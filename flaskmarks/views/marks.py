# flaskmarks/views/profile.py

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
    json
)
from flask_login import login_user, logout_user, login_required

from bs4 import BeautifulSoup as BSoup
from readability.readability import Document
from urllib.request import urlopen
from datetime import datetime
from urllib.parse import urlparse, urljoin
import feedparser
from gensim.summarization import keywords

from ..core.setup import app, db
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

    results = Mark.query.whoosh_search(q).filter(Mark.owner_id == g.user.id).paginate(page, 50, False)


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

        if not form.title.data:
            full_html = urlopen(form.url.data)
            html = full_html.read()
            soup = BSoup(urlopen(form.url.data))
            m.title = soup.title.string

            readable_html = Document(html).summary()

            soup_page = BSoup(full_html)
            m.full_html = readable_html
            
            
            # Add tags and keywords here
            auto_tags_full = keywords(readable_html).split('\n')
            
            for auto_tag in auto_tags_full[:5]:
                m.tags.append(Tag(auto_tag))
            
            #m.full_html = u' '.join(readable_html).encode('utf-8').strip()


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
        m.clicks = mclicks + 1
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



###################
# Import Firefox JSON #
###################
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
                app.logger.debug(e)
                flash('Exception %s, not added. %s'
                        % (bookmark['uri'], e), category='danger')
      
      
###################
# Import mark from uri #
###################
def new_imported_mark(uri):
    u = g.user
    m = Mark(u.id)
    m.type = 'bookmark'
    #https://lpi.oregonstate.edu/mic/


    app.logger.debug(uri)
    full_html = urlopen(uri)
    
    html = full_html.read()
    app.logger.debug(html)
    soup = BSoup(html, 'html.parser')
    app.logger.debug("soup")
    app.logger.debug(soup)
    
    m.title = soup.title.string
    
    m.url = uri
    readable_html = Document(html).summary()

    m.full_html = readable_html
    
    auto_tags_full = keywords(readable_html).split('\n')
    for auto_tag in auto_tags_full[:5]:
        m.tags.append(Tag(auto_tag))
                    
    db.session.add(m)
    db.session.commit()
    
    flash('New %s: "%s", added.'
            % (type, m.title), category='success')
    
    return redirect(url_for('marks.allmarks'))

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
        try:
            data = json.loads(form.file.data.read())
        except Exception as detail:
            flash('%s' % (detail), category='danger')
            return redirect(url_for('profile.view'))
        count = 0
        
        #firefox export
        if 'children' in data:
            iterdict(data)
        
        #bookmarko export
        if 'marks' in data:
            for c in data['marks']:
                m = Mark(u.id)
                m.insert_from_import(c)
                count += 1
                db.session.add(m)
                db.session.commit()
                
        flash('%s marks imported' % (count), category='success')
        return redirect(url_for('profile.userprofile'))
    """
    GET
    """
    return render_template('profile/import.html',
                           form=form)


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
