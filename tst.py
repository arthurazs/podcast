from flask import Flask, render_template, request, redirect, url_for, flash
from flask import g, Markup
from sqlite3 import Row as s_row, connect as s_connect
from feedparser import parse as f_parse
from logging import INFO
from time import strftime


app = Flask(__name__)
app.secret_key = 'dev'
app.logger.setLevel(INFO)
DATABASE = 'database.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = s_connect(DATABASE)
        db.row_factory = s_row
    return db, db.cursor()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/add/', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        link = request.form['podcast']
        name = None
        if link:

            db, cursor = get_db()

            cursor.execute('SELECT name FROM podcasts \
                            WHERE link = ? COLLATE NOCASE', (link,))

            podcast = cursor.fetchone()
            if podcast:
                name = podcast['name']
            else:
                rss = f_parse(link)

                if not rss.entries:
                    flash(f'''There's no content for '{link}'!''')
                    return render_template('add.html')

                name = rss.feed.get('title')
                image = rss.feed.get('image')
                data = {
                    'name': name,
                    'image': image.get('href') if image else None,
                    'link': link,
                    'description': Markup(rss.feed.get('summary')).striptags()
                }

                cursor.execute(
                    'INSERT INTO podcasts(name, description, link, image) \
                     VALUES(:name, :description, :link, :image)', data)

                p_id = cursor.lastrowid
                for entry in rss.entries:
                    episode = {
                        'podcast': p_id,
                        'title': entry.title,
                        'description': Markup(entry.summary).striptags(),
                        'link': entry.link,
                        'mp3': entry.links[1].get('href', None),
                        'published': strftime('%Y-%m-%d %H:%M:%S',
                                              entry.published_parsed)
                    }
                    db.execute(
                        'INSERT INTO podcast_episodes(podcast, title, \
                            description, link, mp3, published) VALUES( \
                            :podcast, :title, :description, :link, :mp3, \
                            :published)', episode)
                db.commit()
        return redirect(url_for('home', name=name))
    return render_template('add.html')


@app.route('/list/')
def list_podcasts():
    app.logger.info(f'Selecting list of podcasts...')
    db, cursor = get_db()
    cursor.execute('SELECT name, image, description FROM podcasts LIMIT 10')
    rows = cursor.fetchall()
    return render_template('list.html', rows=rows)


@app.route('/')
def index():
    app.logger.info(f'Selecting all episodes...')
    db, cursor = get_db()
    cursor.execute('SELECT pod.name, pod.image, epi.title, epi.description, \
                    epi.link, epi.mp3 \
                    FROM podcast_episodes AS epi JOIN podcasts AS pod \
                    ON epi.podcast == pod.id order by published desc LIMIT 10')
    episodes = []
    for row in cursor.fetchall():
        episode = {
            'name': row['name'],
            'image': row['image'],
            'title': row['title'],
            'description': row['description'],
            'link': row['link'],
            'mp3': row['mp3']
        }
        episodes.append(episode)
    return render_template('podcast.html', episodes=episodes)


@app.route('/podcast/')
@app.route('/podcast/<name>')
def home(name=None):
    if name:
        app.logger.info(f'Checking if {name} is on DB...')
        db, cursor = get_db()
        cursor.execute(
            'SELECT id, name, link, image FROM podcasts \
            WHERE name = ? COLLATE NOCASE', (name,))

        podcast = cursor.fetchone()
        if podcast:
            app.logger.info(f'Found {name} on DB...')
            p_id = podcast['id']
            cursor.execute('SELECT title, description, link, mp3 \
                            FROM podcast_episodes WHERE podcast = ? \
                            ORDER BY published DESC LIMIT 10', (p_id, ))

            episodes = []
            for row in cursor.fetchall():
                episode = {
                    'name': podcast['name'],
                    'link': podcast['link'],
                    'image': podcast['image'],
                    'title': row['title'],
                    'description': row['description'],
                    'link': row['link'],
                    'mp3': row['mp3']
                }
                episodes.append(episode)

        else:
            app.logger.info(f'Podcast {name} not found...')
            flash(f'{name} not found in the system, \
                  please add the link to the feed!')
            return redirect(url_for('add'))

        return render_template('podcast.html', episodes=episodes)
    return redirect(url_for('list_podcasts'))


# init
with app.app_context():
    app.logger.info('Starting DB...')
    db, cursor = get_db()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS podcasts(
            id INTEGER PRIMARY KEY, name TEXT, description TEXT,
            link TEXT UNIQUE, image TEXT)''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS podcast_episodes(
            id INTEGER PRIMARY KEY, podcast INTEGER NOT NULL, title TEXT,
            description TEXT, link TEXT UNIQUE, mp3 TEXT UNIQUE,
            published TEXT, FOREIGN KEY(podcast) REFERENCES podcasts(id) \
            ON DELETE CASCADE)''')

    db.commit()
