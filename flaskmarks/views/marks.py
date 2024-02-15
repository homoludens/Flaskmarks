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

from ..core.setup import app, db
from ..core.error import is_safe_url
from ..core.marks_import_thread import MarksImportThread

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
from itertools import islice
from time import sleep
import concurrent.futures
# from flask_whooshee import Whooshee
from sqlalchemy.sql import text

from sqlalchemy_fulltext import FullText, FullTextSearch
import sqlalchemy_fulltext.modes as FullTextMode
# Suppress warning
# https://github.com/mengzhuo/sqlalchemy-fulltext-search/issues/21
FullTextSearch.inherit_cache = False

status = 0
total_lines = 0

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
    return redirect(url_for('marks.recently_added'))


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

    results = Mark.query.session.query(Mark)\
                        .filter(FullTextSearch(q, Mark, FullTextMode.NATURAL))\
                        .filter(Mark.owner_id == g.user.id)\
                        .paginate(page=page, per_page=5, error_out=False)

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
            r = MarksImportThread(form.url.data, u.id)
            m = r.run()
            
        flash('New %s: "%s", added.' % (type, m['title']), category='success')
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
                # new_imported_mark(bookmark['uri'])
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


def thread_import_file(text_file_path, app, user_id):
    maxthreads = 20
    global status
    global total_lines
    status = 0
    i = 0

    with open(text_file_path) as fp:
        while True:
            lines_gen = islice(fp, maxthreads)
            # print(list(lines_gen))
            lines_new = []
            for line in lines_gen:
                status += 1
                # line = fp.readline()
                if not lines_gen:
                    break
                print("Line{}: {}".format(status, line.strip()))
                url = line.strip()
                lines_new.append(url)

            with concurrent.futures.ThreadPoolExecutor(max_workers=maxthreads) as exe:
                zip( lines_new, [user_id] * len(lines_new) )
                result = exe.map(marks_import_threads, zip( lines_new, [user_id] * len(lines_new)))


def marks_import_threads(url_user_id):
    url, user_id = url_user_id
    r = MarksImportThread(url, user_id)
    r.run()


@marks.route('/marks/import', methods=['GET', 'POST'])
@login_required
def import_marks():
    global status
    global total_lines
    # total_lines = 0

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

            with open(text_file_path) as fp:
                for total_lines, line in enumerate(fp):
                    pass

            print('Total Lines', total_lines + 1)

            t1 = Thread(target=thread_import_file, args=(text_file_path, current_app._get_current_object(), u.id))
            t1.start()

        flash('%s marks imported' % (count), category='success')
        return render_template('profile/import_progress.html', total_lines=total_lines, status=1 )
    
    status = 0
    
    return render_template('profile/import_progress.html', form=form, status=0)
  

@app.route('/marks/import/status', methods=['GET', 'POST'])
@login_required
def getStatus():
  global status
  global total_lines
  statusList = {'status':status, 'total_lines': total_lines}
  return json.dumps(statusList)

# Threaded import - end

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
