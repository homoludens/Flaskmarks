# flaskmarks/views/profile.py
import threading
from flask.globals import _request_ctx_stack
from flask import (
    Blueprint,
    render_template,
    flash,
    redirect,
    url_for,
    g,
    request,
    abort,
    jsonify,
    json,
    current_app
)
from flask_login import login_user, logout_user, login_required
from werkzeug.utils import secure_filename
import os
# from bs4 import BeautifulSoup as BSoup
from readability.readability import Document
from urllib.request import urlopen
from datetime import datetime
from urllib.parse import urlparse, urljoin
import feedparser
from typing import Iterable
from newspaper import Article, ArticleBinaryDataException
#from gensim.summarization import keywords
from werkzeug.utils import secure_filename
import tldextract

from ..core.setup import app, db
from ..core.youtube import get_youtube_info, check_url_video
from ..core.error import is_safe_url
from ..forms import (
    LoginForm,
    MarkForm,
    MarkEditForm,
    YoutubeMarkForm,
    UserRegisterForm,
    UserProfileForm,
    MarksImportForm
)
from ..models import Mark
from ..models.tag import Tag

import logging
from urllib.parse import urlparse

from threading import Thread
from time import sleep
import concurrent.futures

pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def uri_validator(url_to_test):
    """
    Validate URL
    return true or false
    """
    try:
        result = urlparse(url_to_test)
        return all([result.scheme, result.netloc])
    except:
        return False
    
logging.basicConfig(filename='record.log', level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

marks = Blueprint('marks', __name__)


@marks.route('/')
@marks.route('/index')
def webroot():
    return redirect(url_for('marks.allmarks'))


@marks.route('/marks/all')
@marks.route('/marks/all/<int:page>')
@login_required
def allmarks(page=1):
    u = g.user
    return render_template('mark/index.html',
                           title='Marks - page %d' % page,
                           header='',
                           marks=u.marks(page))


@marks.route('/marks/sort/clicked')
@marks.route('/marks/sort/clicked/<int:page>')
@login_required
def recently_clicked(page=1):
    u = g.user
    return render_template('mark/index.html',
                           title='Marks - page %d' % page,
                           header='',
                           marks=u.recent_marks(page, 'clicked'))


@marks.route('/marks/sort/recently')
@marks.route('/marks/sort/recently/<int:page>')
@login_required
def recently_added(page=1):
    u = g.user
    return render_template('mark/index.html',
                           title='Marks - page %d' % page,
                           header='',
                           marks=u.recent_marks(page, 'added'))


@marks.route('/marks/search/tag/<slug>')
@marks.route('/marks/search/tag/<slug>/<int:page>')
@login_required
def mark_q_tag(slug, page=1):
    return render_template('mark/index.html',
                           title='Marks with tag: %s' % (slug),
                           header='Marks with tag: %s' % (slug),
                           marks=g.user.q_marks_by_tag(slug, page))


@marks.route('/marks/search/string', methods=['GET'])
@marks.route('/marks/search/string/<int:page>', methods=['GET'])
@login_required
def search_string(page=1):
    q = request.args.get('q')
    t = request.args.get('type')

    if not q and not t:
        return redirect(url_for('marks.allmarks'))

    #m = g.user.q_marks_by_string(page, q, t)

    results = Mark.query.whoosh_search(q).filter(Mark.owner_id == g.user.id).paginate(page=page, per_page=50, error_out=False)


    #print results

    #print m

    return render_template('mark/index.html',
                           title='Search results for: %s' % (q),
                           header="Search results for: '%s'" % (q),
                           marks=results)


@marks.route('/mark/new', methods=['GET'])
@login_required
def new_mark_selector():
    return render_template('mark/new_selector.html',
                           title='Select new mark type')



@marks.route('/mark/new/<string:type>', methods=['GET', 'POST'])
@login_required
def new_mark(type):
    u = g.user
    if type not in ['bookmark', 'feed', 'youtube']:
        abort(404)

    if type == 'youtube':
        form = YoutubeMarkForm()
    else:
        form = MarkForm()
    """
    POST
    """
    if form.validate_on_submit():
        """ Check if a mark with this urs exists."""
        if g.user.q_marks_by_url(form.url.data):
            flash('Mark with this url "%s" already\
                  exists.' % (form.url.data), category='danger')
            return redirect(url_for('marks.allmarks'))
        m = Mark(u.id)
        form.populate_obj(m)
        m.type = type

        # if no title we will get title and text
        if not form.title.data:
            
            #newspaper3k
            url = form.url.data
            article = Article(url)
            article.download()
            full_html = article.html

            readable = Document(full_html)
            readable_html = readable.summary()
            readable_title = readable.title()
            
            m.title = readable_title
            m.full_html = readable_html
            
            article.parse()
            article.nlp()
            # Add tags and keywords here            
            for auto_tag in article.keywords[:5]:
                m.tags.append(Tag(auto_tag))
                
            m.description = article.summary

        db.session.add(m)
        db.session.commit()
        flash('New %s: "%s", added.'
              % (type, m.title), category='success')
        return redirect(url_for('marks.allmarks'))
    """
    GET
    """
    return render_template('mark/new_%s.html' % (type),
                           title='New %s' % (type),
                           form=form)


@marks.route('/mark/view/<int:id>/<string:type>', methods=['GET'])
@login_required
def view_mark(id, type):
    m = g.user.get_mark_by_id(id)
    if not m:
        abort(403)

    if m.type not in m.valid_feed_types:
        abort(404)

    data = feedparser.parse(m.url)

    m.clicks = m.clicks + 1
    m.last_clicked = datetime.utcnow()
    db.session.add(m)
    db.session.commit()

    return render_template('mark/view_%s.html' % (type),
                           mark=m,
                           data=data,
                           title=m.title,
                           )


@marks.route('/mark/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_mark(id):
    m = g.user.get_mark_by_id(id)
    form = MarkEditForm(obj=m)
    if not m:
        abort(403)
    """
    POST
    """
    if form.validate_on_submit():
        if m.url != form.url.data and g.user.q_marks_by_url(form.url.data):
            flash('Mark with this url (%s) already\
                  exists.' % (form.url.data), category='danger')
            return redirect(url_for('marks.allmarks'))
        form.populate_obj(m)
        m.updated = datetime.utcnow()
        db.session.add(m)
        db.session.commit()
        flash('Mark "%s" updated.' % (form.title.data), category='success')
        if form.referrer.data and is_safe_url(form.referrer.data):
            return redirect(form.referrer.data)
        return redirect(url_for('marks.allmarks'))
    """
    GET
    """
    form.referrer.data = request.referrer
    return render_template('mark/edit.html',
                           mark=m,
                           title='Edit mark - %s' % m.title,
                           form=form
                           )


@marks.route('/mark/viewhtml/<int:id>', methods=['GET', 'POST'])
@login_required
def view_html_mark(id):
    m = g.user.get_mark_by_id(id)
    if not m:
        abort(403)
    return render_template('mark/view_html.html',
                           mark=m,
                           title='View html for mark - %s' % m.title,
                           )



@marks.route('/mark/delete/<int:id>')
@login_required
def delete_mark(id):
    m = g.user.get_mark_by_id(id)
    if m:
        db.session.delete(m)
        db.session.commit()
        flash('Mark "%s" deleted.' % (m.title), category='info')
        """
        if request.referrer and is_safe_url(request.referrer):
            return redirect(request.referrer)
        """
        return redirect(url_for('marks.allmarks'))
    abort(403)


########
# AJAX #
########
@marks.route('/mark/inc')
@login_required
def ajax_mark_inc():
    if request.args.get('id'):
        id = int(request.args.get('id'))
        m = g.user.get_mark_by_id(id)
        if not m:
            return jsonify(status='forbidden')
        m.clicks = m.clicks + 1
        m.last_clicked = datetime.utcnow()
        db.session.add(m)
        db.session.commit()
        return jsonify(status='success')
    return jsonify(status='error')


###################
# Import / Export #
###################
@marks.route('/marks/export.json', methods=['GET'])
@login_required
def export_marks():
    u = g.user
    d = [{'title': m.title,
          'type': m.type,
          'url': m.url,
          'clicks': m.clicks,
          'last_clicked': m.last_clicked,
          'created': m.created.strftime('%s'),
          'updated': m.updated.strftime('%s') if m.updated else '',
          'tags': [t.title for t in m.tags]}
         for m in u.all_marks()]
    return jsonify(marks=d)


#######################
# Import Firefox JSON #
#######################
def iterdict(d):
  app.logger.info('Info level log')
  i = 0
  if 'children' in d:
    iterdict(d['children'])
  else:
      for bookmark in d:
        if 'children' in bookmark:
            iterdict(bookmark['children'])  
        if 'uri' in bookmark: 
            i = i + 1
            try:
                app.logger.debug(bookmark['uri'])
                new_imported_mark(bookmark['uri'])
            except Exception as e:
                app.logger.error(e)
                # app.logger.error('Exception %s, not added. %s' % (bookmark['uri'], e))
                # print('Exception %s, not added. %s' % (bookmark['uri'], e))


def iterdict2(d):
    """
    data = json.load(open('file.json'))
    a = iterdict2(data)
    """
    i = 0
    final_list = []
    if 'children' in d:
        l = iterdict2(d['children'])
        final_list.append(l)
    else:
        for bookmark in d:
            if 'children' in bookmark:
                l = iterdict2(bookmark['children'])
                final_list.append(l)
            if 'uri' in bookmark:
                i = i + 1
                print(i)
                try:
                    uri = bookmark['uri']
                    final_list.append(uri)
                    # print(bookmark['uri'])

                    # print(bookmark.keys())
                except Exception as e:
                    print(f"Exception: {e}")
                    uri = ''
    return list(flatten(final_list))


def flatten(items):
    """Yield items from any nested iterable; see Reference."""
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x


###################
# Import mark from uri #
###################
def new_imported_mark(url):

    if g.user.q_marks_by_url(url):
        app.logger.debug('Mark with this url "%s" already exists.' % (url))
        return redirect(url_for('marks.allmarks'))

    print(f"new_imported_mark: {url}")
    # test if it looks like url
    if not uri_validator(url):
        print("not valid uri")
        return redirect(url_for('marks.allmarks'))


    url_domain = tldextract.extract(url).domain
    readable_title = None

    u = g.user
    m = Mark(u.id)
    m.type = 'bookmark'
    # https://lpi.oregonstate.edu/mic/

    m.url = url
    m.title = url
    soup_page = False

    existing_mark = Mark.query.filter(Mark.url == url).all()
    if len(existing_mark) > 0:
        print('Existing bookmark %s: "%s", added.' % (type, m.title))
        # flash('Existing bookmark %s: "%s", added.' % (type, m.title), category='success')
        return redirect(url_for('marks.allmarks'))
    else:
        if url_domain in ['google1', 'upwork1', 'qlik1']:
            m.tags.append(Tag(url_domain))

            db.session.add(m)
            db.session.commit()

            return redirect(url_for('marks.allmarks'))
        
        elif url_domain in ['youtube', 'youtu'] and check_url_video(url):
            print(url_domain)
            youtube_info_dict = get_youtube_info(url)
            m.title = youtube_info_dict['title']
            m.description = youtube_info_dict['description']
            youtube_info_dict['subtitles'] = youtube_info_dict['subtitles'].replace('\n', '<br/>')
            m.full_html = youtube_info_dict['description'] +  youtube_info_dict['subtitles']

            m.tags.append(Tag(url_domain))
            m.tags.append(Tag('video'))

            # some videos don't have channel
            if youtube_info_dict['uploader']: 
                m.tags.append(Tag(youtube_info_dict['uploader']))

            for auto_tag in youtube_info_dict['tags']:
                m.tags.append(Tag(auto_tag))

            db.session.add(m)
            db.session.commit()
            return redirect(url_for('marks.allmarks'))

        article = Article(url)

        try:
            article.download()
        except ArticleBinaryDataException:
            print(f"URL {url} is binary data")
            
        try:
            article.parse()
            article.nlp()
        except:
            print(f"Article {url} not working: article not able to be parsed")
        else:
            if article.is_parsed:
                full_html = article.html
                # soup_page = BSoup(full_html, features="lxml")

                if full_html:
                    readable = Document(full_html)
                    readable_html = readable.summary()
                    readable_title = readable.title()
                    m.full_html = readable_html
                    m.description = article.summary
                else:
                    m.full_html = article.summary
                    m.description = article.summary
            else:
                m.full_html = url

            if readable_title:
                m.title = readable_title
            else:
                m.title = url
            
            
            # Add tags and keywords here
            m.tags.append(Tag(url_domain))

            for auto_tag in article.keywords[:5]:
                m.tags.append(Tag(auto_tag))
                
    db.session.add(m)
    db.session.commit()
    print('New %s: "%s", added.' % (type, m.title))

    
    return redirect(url_for('marks.allmarks'))


# def prepare_new_import_thread(url):
#     if g.user.q_marks_by_url(url):
#         app.logger.debug('Mark with this url "%s" already exists.' % (url))
#         return redirect(url_for('marks.allmarks'))
    
#     if not uri_validator(url):
#         print("not valid uri")
#         return redirect(url_for('marks.allmarks'))
    
#     u = g.user
#     m = Mark(u.id)


#     db.session.add(m)
#     db.session.commit()


# custom thread
class ImportMarksThread(Thread):
    # constructor
    def __init__(self, url):
        # execute the base constructor
        Thread.__init__(self)
        # set a default value
        self.url = url
        self.m = None
 
    # function executed in a new thread
    def run(self):
        # block for a moment
        sleep(1)
        # store data in an instance variable
        self.value = 'Hello from a new thread'


        url = self.url

        print(f"Total Active threads are {threading.activeCount()}")

        print(f"new_imported_mark_thread: {url}")
        
        url_domain = tldextract.extract(url).domain
        readable_title = None

        m = {}
        m['type'] = 'bookmark'
        m['tags'] = []

        m['url'] = url
        m['title'] = url
        
        soup_page = False

        if url_domain in ['youtube', 'youtu'] and check_url_video(url):
            print(url_domain)
            youtube_info_dict = get_youtube_info(url)
            m['title'] = youtube_info_dict['title']
            m['description'] = youtube_info_dict['description']
            youtube_info_dict['subtitles'] = youtube_info_dict['subtitles'].replace('\n', '<br/>')
            m['full_html'] = youtube_info_dict['description'] +  youtube_info_dict['subtitles']
            
            m['tags'].append(url_domain)
            m['tags'].append('video')

            # some videos don't have channel
            if youtube_info_dict['uploader']:
                m['tags'].append(youtube_info_dict['uploader'])

            for auto_tag in youtube_info_dict['tags']:
                m['tags'].append(auto_tag)

            self.m = m
            return 

        article = Article(url)

        try:
            article.download()
        except ArticleBinaryDataException:
            print(f"URL {url} is binary data")
            
        try:
            article.parse()
            article.nlp()
        except:
            print(f"Article {url} not working: article not able to be parsed")
        else:
            if article.is_parsed:
                full_html = article.html
                # soup_page = BSoup(full_html, features="lxml")

                if full_html:
                    readable = Document(full_html)
                    readable_html = readable.summary()
                    readable_title = readable.title()
                    m['full_html']  = readable_html
                    m['description'] = article.summary
                else:
                    m['full_html']  = article.summary
                    m['description'] = article.summary
            else:
                m['full_html']  = url

            if readable_title:
                m['title'] = readable_title
            else:
                m['title']  = url
            
            # Add tags and keywords here
            m['tags'].append(url_domain)

            for auto_tag in article.keywords[:5]:
                m['tags'].append(auto_tag)
                    
        print('New %s: "%s", added.' % (type,  m['title'] ))
        
        self.m = m
        return        


def new_imported_mark_thread(url):
    print(f"Total Active threads are {threading.activeCount()}")

    print(f"new_imported_mark_thread: {url}")
    
    url_domain = tldextract.extract(url).domain
    readable_title = None

    m = {}
    m['type'] = 'bookmark'
    m['tags'] = []

    m['url'] = url
    m['title'] = url
    
    soup_page = False

    if url_domain in ['youtube', 'youtu'] and check_url_video(url):
        print(url_domain)
        youtube_info_dict = get_youtube_info(url)
        m['title'] = youtube_info_dict['title']
        m['description'] = youtube_info_dict['description']
        youtube_info_dict['subtitles'] = youtube_info_dict['subtitles'].replace('\n', '<br/>')
        m['full_html'] = youtube_info_dict['description'] +  youtube_info_dict['subtitles']
        
        m['tags'].append(Tag( url_domain))
        m['tags'].append(Tag('video'))

        # some videos don't have channel
        if youtube_info_dict['uploader']:
            m['tags'].append(Tag(youtube_info_dict['uploader']))
            pass

        for auto_tag in youtube_info_dict['tags']:
            m['tags'].append(Tag(auto_tag))

        return m

    article = Article(url)

    try:
        article.download()
    except ArticleBinaryDataException:
        print(f"URL {url} is binary data")
        
    try:
        article.parse()
        article.nlp()
    except:
        print(f"Article {url} not working: article not able to be parsed")
    else:
        if article.is_parsed:
            full_html = article.html
            # soup_page = BSoup(full_html, features="lxml")

            if full_html:
                readable = Document(full_html)
                readable_html = readable.summary()
                readable_title = readable.title()
                m['full_html']  = readable_html
                m['description'] = article.summary
            else:
                m['full_html']  = article.summary
                m['description'] = article.summary
        else:
            m['full_html']  = url

        if readable_title:
            m['title'] = readable_title
        else:
            m['title']  = url
        
        # Add tags and keywords here
        m['tags'].append(Tag(url_domain))

        for auto_tag in article.keywords[:5]:
            m['tags'].append(Tag(auto_tag))
                
    print('New %s: "%s", added.' % (type,  m['title'] ))
    
    return m


def thread_import_file(text_file_path, app, user_id):

    global status
    status = 0 

    with open(text_file_path) as fp:
        while True:
            status += 1
            line = fp.readline()
            if not line:
                break
            print("Line{}: {}".format(status, line.strip()))
            url = line.strip()
            maxthreads = 4
            print("MAIN  Total Active threads are {0}".format(threading.activeCount()))
            if threading.activeCount() <= maxthreads:
                thread = ImportMarksThread(url)
                thread.start()
                thread.join()
                data = thread.m

                with app.app_context():
                    m = Mark(user_id)
                    m.url = data['url']
                    m.title = data['title']
                    m.description = data['title']
                    m.full_html = data['title']
                    m.type = data['title']

                    for auto_tag in data['tags']:
                        m.tags.append(Tag(auto_tag))

                    db.session.add(m)
                    db.session.commit()
    

@app.route('/marks/import/thread', methods=['GET', 'POST'])
@login_required
def import_marks_thread():
    global status

    app.logger.error('Processing default request')
    u = g.user
    form = MarksImportForm(obj=u)

    if form.validate_on_submit():
        f = form.file.data
        filename = secure_filename(f.filename)
        f.save(os.path.join(
            app.root_path, 'files', filename
        ))
        
        if f.content_type == 'text/plain':
            count = 0
            text_file_path = os.path.join(
                app.root_path, 'files', filename
            )

            t1 = Thread(target=thread_import_file, args=(text_file_path, current_app._get_current_object(), u.id))
            t1.start()

        flash('%s marks imported' % (count), category='success')
        return render_template('profile/import_progress.html', status=1)
    
    
    status = 0
    return render_template('profile/import_progress.html', form=form, status=0)

    return render_template('profile/import_progress.html')
  

@app.route('/marks/import/status', methods=['GET', 'POST'])
@login_required
def getStatus():
  statusList = {'status':status}
  return json.dumps(statusList)

# Threaded import - end

@marks.route('/marks/import', methods=['GET', 'POST'])
@login_required
def import_marks():
    
    app.logger.error('Processing default request')
    u = g.user
    form = MarksImportForm(obj=u)
    """
    POST
    """
    if form.validate_on_submit():
        f = form.file.data
        filename = secure_filename(f.filename)
        f.save(os.path.join(
            app.root_path, 'files', filename
        ))
        
        if f.content_type == 'application/json':
            # os.path.join( app.root_path, 'files', filename)
            try:
                # data = json.loads(form.file.data.read())
                # with os.path.join( app.root_path, 'files', filename) as fp:
                fp = open(os.path.join( app.root_path, 'files', filename) ) 
                data = json.load(fp)
                # fp.close()
            except Exception as detail:
                flash('%s' % (detail), category='danger')
                return redirect('/marks/import')
            count = 0
            
            #import firefox export
            if 'children' in data:
                # iterdict(data)
                links = iterdict2(data)
                for link in links:
                    try:
                        app.logger.debug(link)
                        new_imported_mark(link)
                    except Exception as e:
                        app.logger.error(e)
                    else:
                        app.logger.debug(f"{link} added")
            
            #import bookmarko export
            elif 'marks' in data:
                for c in data['marks']:
                    m = Mark(u.id)
                    m.insert_from_import(c)
                    count += 1
                    db.session.add(m)
                    db.session.commit()
            
            # fp.close()

        # import from plain text file, each line is url
        elif f.content_type == 'text/plain':
            count = 0
            text_file_path = os.path.join(
                app.root_path, 'files', filename
            )
            with open(text_file_path) as fp:
                while True:
                    count += 1
                    line = fp.readline()
                    if not line:
                        break
                    print("Line{}: {}".format(count, line.strip()))
                    try:
                        new_imported_mark(line.strip())
                    except Exception as e:
                        print('exception', e)
                        app.logger.error(f"Exception {line.strip()}, {e}")
                
                
        flash('%s marks imported' % (count), category='success')
        return redirect('all')
    """
    GET
    """
    # fp.close()
    return render_template('profile/import.html', form=form)


#########
# Other #
#########
@marks.route('/mark/redirect/<int:id>')
@login_required
def mark_redirect(id):
    url = url_for('marks.mark_meta', id=id)
    return render_template('meta.html', url=url)


@marks.route('/meta/<int:id>')
@login_required
def mark_meta(id):
    m = g.user.get_mark_by_id(id)
    if m:
        m.clicks = m.clicks + 1
        m.last_clicked = datetime.utcnow()
        db.session.add(m)
        #db.session.commit()
        return render_template('meta.html', url=m.url)
    abort(403)
