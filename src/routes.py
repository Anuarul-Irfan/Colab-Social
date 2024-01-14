from flask import request, jsonify, redirect, url_for,render_template,flash
from src.models import *
from src import app,db
from datetime import datetime
import json
import os
from flask_pagedown import PageDown
from src.forms import PostForm,CommentForm
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import UserMixin, current_user, LoginManager, login_required, login_user, logout_user
from flask_dance.consumer.storage.sqla import  SQLAlchemyStorage
from flask_dance.consumer import oauth_authorized
from sqlalchemy.orm.exc import NoResultFound
from flaskext.markdown import Markdown
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import session



sentry_sdk.init(
    dsn="https://876ab5e99d654526bac15ea4206d59cf@sentry.io/2358653",
    integrations=[FlaskIntegration()]
)

"""
 Library initialization and configurations Setups
"""
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = "1"
GOOGLE_CLIENT_ID=os.environ.get('936649164386-005qv70d2iq0c55lhhh2p4tua6v3ehdq.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET=os.environ.get('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')
login_manager = LoginManager(app)
login_manager.init_app(app)
pagedown = PageDown(app)
markdown=Markdown(app)

"""
   Google authentication and authorization Section
"""
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_handler():
    return '<h2 style="color:red">You not authorized to visit this page, 401 <h2>'

@app.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(request.referrer)
    else:
        redirect_url = 'https://accounts.google.com/o/oauth2/auth'
        query_params = {
            'response_type': 'code',
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': 'https://yourdomain.com/oauth2callback',
            'scope': 'https://www.googleapis.com/auth/userinfo.email',
            'state': 'random_state_string',
        }
        final_url = requests.Request('GET', url=redirect_url, params=query_params).prepare().url
        return redirect(final_url)

@app.route('/oauth2callback')
def google_oauth2_authcode_callback():
    if 'error' in request.args:
        return Response('Error occurred during authentication')

    auth_code = request.args['code']
    oauth_link = 'https://accounts.google.com/o/oauth2/token'
    post_params = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': 'https://nuarul.pythonanywhere.com//oauth2callback',
    }

    result = requests.post(oauth_link, data=post_params).json()
    access_token = result['access_token']

    google_plus_user_info_api = 'https://www.googleapis.com/userinfo/v2/me'
    hidden_headers = {'Authorization': 'Bearer {}'.format(access_token)}
    user_info = requests.get(google_plus_user_info_api, headers=hidden_headers).json()

    user_id = str(user_info['id'])
    query = OAuth.query.filter_by(provider='google', provider_user_id=user_id)
    try:
        oauth = query.one()
    except NoResultFound:
        oauth = OAuth(
            provider='google',
            provider_user_id=user_id,
            token=result,
        )
    if oauth.user:
        login_user(oauth.user)
        print("Successfully signed in with Google")
    else:
        user = User(name=user_info["name"],picture=user_info["picture"],user_type=UserTypeEnum.CASUAL)
        oauth.user = user
        db.session.add_all([user, oauth])
        db.session.commit()
        login_user(user)
        print("Successfully signed in with Google.")
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))   


"""

Routes and Business login section

"""

@app.route('/create',methods=['GET','POST'])   
def create():
    form =PostForm()
    if request.method=='POST' and current_user.is_authenticated:
        if form.validate_on_submit():
            title=form.title.data
            content=form.content.data
            post=Comment(title=title,content=content,author=current_user,parent=None)
            db.session.add(post)
            db.session.commit()
            current_user.score=current_user.score+10
            current_user.post_count=current_user.post_count+1
            db.session.commit()
            return redirect(url_for('index'))
    if request.method=='POST' and current_user.is_authenticated==False:
        flash('Login Required')
        return redirect(url_for('index'))
    posts_list=Comment.query.filter(Comment.parent_id==None,Comment.is_deleted==False).order_by(Comment.created_at.desc()).all()
    return render_template('index.html',posts=posts_list,form=form)

@app.route('/',methods=['GET','POST'])   
def index():
    form = PostForm()
    if request.method=='POST' and current_user.is_authenticated:
        if form.validate_on_submit():
            title=form.title.data
            content=form.content.data
            post=Comment(title=title,content=content,author=current_user,parent=None)
            db.session.add(post)
            db.session.commit()
            current_user.score=current_user.score+10
            current_user.post_count=current_user.post_count+1
            db.session.commit()
            return redirect(url_for('index'))
    if request.method=='POST' and current_user.is_authenticated==False:
        flash('Login Required')
        return redirect(url_for('index'))
    posts_list=Comment.query.filter(Comment.parent_id==None,Comment.is_deleted==False).order_by(Comment.created_at.desc()).all()
    return render_template('home.html',posts=posts_list,form=form)

@app.route('/profile/<int:user_id>') 
def profile(user_id):
    posts=Comment.query.filter(Comment.user_id==user_id,Comment.parent_id==None,Comment.is_deleted==False).all()
    user=User.query.filter_by(id=user_id).first()
    return render_template('profile.html',posts=posts,user=user)

@app.route('/trending') 
def trending_page():
    posts=Comment.query.filter(Comment.parent_id==None,Comment.is_deleted==False).order_by(Comment.likes.desc(),Comment.created_at.desc()).all()
    top_users=User.query.order_by(User.score.desc()).limit(5).all()
    return render_template('trending.html',posts=posts,top_users=top_users)


@app.route('/post/<int:post_id>',methods=['GET','POST'])
def post_detail(post_id):
    form=CommentForm()
    post=Comment.query.filter_by(id=post_id).first()
    if request.method=='POST' and current_user.is_authenticated:
        if form.validate_on_submit():
            content=form.content.data
            comment=Comment(content=content,author=current_user,parent=post)
            db.session.add(comment)
            db.session.commit()
            current_user.score=current_user.score+5
            db.session.commit()
            return redirect(url_for('post_detail', post_id=post_id))
    if request.method=='POST' and current_user.is_authenticated==False:
        flash('Login Required')
        return redirect(request.referrer)
    comments = Comment.query.filter_by(parent_id=post_id).order_by(Comment.created_at.desc()).all()
    return render_template('detail_post.html',post=post,comments=comments,form=form)


@app.route('/upvote/<post_id>',methods=['GET','POST'])
def upvote(post_id):
    comment = Comment.query.filter_by(id=post_id).first()
    if not current_user.is_authenticated:
        flash('Login Required')
        return redirect(request.referrer)
    if current_user not in comment.liked_by:
        comment.liked_by.append(current_user)
        comment.likes=comment.likes+1
        db.session.commit()
        return redirect(request.referrer)
    flash('You have already upvoted')
    return redirect(request.referrer)


   

"""

    Rest API Section 

"""


@app.route('/api/trending',methods=['GET'])
def trending():
    query_parameters = request.args
    offset=query_parameters['offset']
    limit=query_parameters['limit']
    posts=Comment.query.filter(Comment.parent_id==None,Comment.is_deleted==False).order_by(Comment.likes.desc(),Comment.created_at.desc()).offset(offset).limit(limit).all()
    data=[]
    for post in posts:
        replies = Comment.query.filter_by(parent_id=post.id).all()
        comment_list=[]
        for replie in replies:
            replie_dic={
                "author":replie.author.name,
                "content":replie.content
            }
            comment_list.append(replie_dic)
        post_list={
            "post_id": post.id,
            "opened" : False,
            "author": post.author.name,
            "title":post.title,
            "content": post.content,
            "time": post.get_json()['time'],
            "upvotes": post.likes,
            "comment_list":comment_list

        }
        data.append(post_list)
    return jsonify({"data":data})
      

@app.route('/api/get_posts/<int:user_id>')
def get_posts(user_id):
    posts = Comment.query.filter_by(user_id=user_id).filter_by(parent_id=None).all()
    if len(posts) == 0:
        return jsonify({"messsage":"No Post Available"})
    return jsonify([post.get_json() for post in posts])


@app.route('/api/get_replies/<int:post_id>')
def get_replies(post_id):
    replies = Comment.query.filter_by(parent_id=post_id).all()
    if len(replies) == 0:
        return jsonify({"messsage":"No Comment Available"})
    return jsonify([replie.get_json() for replie in replies])


@app.route('/api/get_all_posts')
def get_all_post():
    posts=Comment.query.filter(Comment.parent_id==None,Comment.is_deleted==False).order_by(Comment.created_at.desc()).all()
    data=[]
    for post in posts:
        replies = Comment.query.filter_by(parent_id=post.id).all()
        comment_list=[]
        for replie in replies:
            replie_dic={
                "author":replie.author.name,
                "content":replie.content
            }
            comment_list.append(replie_dic)
        post_list={
            "post_id": post.id,
            "opened" : False,
            "author": post.author.name,
            "title":post.title,
            "content": post.content,
            "time": post.get_json()['time'],
            "upvotes": post.likes,
            "comment_list":comment_list

        }
        data.append(post_list)
    return jsonify({"data":data})

@app.route('/callback')
def callback():
    pass    
