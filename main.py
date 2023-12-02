import os
import smtplib
import requests
from datetime import date
from functools import wraps
from hashlib import md5

from dotenv import load_dotenv
from flask import Flask, abort, render_template, redirect, url_for, flash, request, jsonify
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor

from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from urllib3.exceptions import HTTPError
from werkzeug.security import generate_password_hash, check_password_hash

from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm, SearchForm

DATA_ARTICLES_COUNT = 40
NUMS_OF_ARTICLES_TO_RENDER = 20
SMTPLIB_CONNECT_NO = 587
INCREMENT = 1
TOP_SEARCH_NUMBER_RENDER = 5
SALT_LENGTH = 10

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///posts.db")
db = SQLAlchemy()
db.init_app(app)

login_manager = LoginManager()
login_manager.session_protection = "strong"
login_manager.login_view = "login"
login_manager.login_message_category = "info"
login_manager.init_app(app)


@login_manager.user_loader
def loader_user(user_id):
    return db.session.get(User, int(user_id))


# CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")
    top_search = relationship("TopSearches", back_populates="user_top_search")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=True)
    subtitle = db.Column(db.String(300), nullable=True)
    date = db.Column(db.String(250), nullable=True)
    body = db.Column(db.Text, nullable=True)
    img_url = db.Column(db.String(500), nullable=True)


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    commenter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    commenter = relationship("User", back_populates="comments")
    blog_post_id = db.Column(db.Integer)
    comments_posted = db.Column(db.Text)


class TopSearches(db.Model):
    __tablename__ = "top_searches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    search_item = db.Column(db.String(300))
    search_count = db.Column(db.Integer)
    user_top_search = relationship("User", back_populates="top_search")


class TotalTopSearches(db.Model):
    __tablename__ = "total_top_searches"
    id = db.Column(db.Integer, primary_key=True)
    search_item = db.Column(db.String(300))
    total_search_count = db.Column(db.Integer)


with app.app_context():
    db.create_all()


# Python Decorator
def admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id > 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()

    if register_form.validate_on_submit():
        user = User.query.filter_by(email=register_form.email.data).first()

        if not user:
            password = generate_password_hash(password=register_form.password.data, method="pbkdf2:sha256",
                                              salt_length=SALT_LENGTH)
            new_user = User(email=register_form.email.data, password=password, name=register_form.name.data)
            db.session.add(new_user)
            db.session.commit()
            user = User.query.filter_by(email=register_form.email.data).first()
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("You've already signed up, with that Email, Login instead")
            return redirect(url_for("login"))

    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():

        user = User.query.filter_by(email=login_form.email.data).first()
        if user:
            if check_password_hash(pwhash=user.password, password=login_form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Password incorrect, please try again")
        else:
            flash("This Email does not exist, please try again")

    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


def news_api(search) -> list:
    header = {"X-Api-Key": os.getenv("APIKEY")
              }
    params = {
        "q": search,
        "language": "en",
        "sortBy": "publishedAt"
    }
    raw_data = requests.get(url="https://newsapi.org/v2/everything?", params=params, headers=header)
    raw_data.raise_for_status()
    data = raw_data.json()
    return data["articles"][:DATA_ARTICLES_COUNT]


def add_new_search_item_to_db(search_name) -> None:
    search_name = search_name.title()

    with app.app_context():
        top_searches = TopSearches.query.filter_by(search_item=search_name).first()

        if top_searches:
            db.get_or_404(TopSearches, top_searches.id).search_count += INCREMENT
            db.session.commit()
            return

        search_json = jsonify(item=search_name, count=INCREMENT, user=current_user.id).json

        new_searches_item = TopSearches(search_item=search_json["item"], search_count=search_json["count"],
                                        user_id=search_json["user"])
        db.session.add(new_searches_item)
        db.session.commit()


def render_top_searches(user_id) -> list:
    search_db = db.get_or_404(User, user_id)
    item_count_tuple = ((item.search_count, item.search_item) for item in search_db.top_search)
    return sorted(list(item_count_tuple), reverse=True)[:TOP_SEARCH_NUMBER_RENDER]


def add_new_search_item_to_general_db(search_name) -> None:
    search_name = search_name.title()

    with app.app_context():
        total_top_searches = TotalTopSearches.query.filter_by(search_item=search_name).first()

        if total_top_searches:
            db.get_or_404(TotalTopSearches, total_top_searches.id).total_search_count += INCREMENT
            db.session.commit()
            return

        search_json = jsonify(item=search_name, count=INCREMENT).json

        new_total_search_item = TotalTopSearches(search_item=search_json["item"],
                                                 total_search_count=search_json["count"])
        db.session.add(new_total_search_item)
        db.session.commit()


def render_general_top_searches() -> list:
    total_searches = db.session.query(TotalTopSearches)
    item_count_tuple = ((item.total_search_count, item.search_item) for item in total_searches)
    return sorted(list(item_count_tuple), reverse=True)[:TOP_SEARCH_NUMBER_RENDER]


def database_api_data_to_render(blog_post_list) -> list:
    for post in blog_post_list:
        yield jsonify(
            id=post.id,
            title=post.title,
            subtitle=post.subtitle,
            author=post.author.name,
            date=post.date
        ).json


@app.route('/', methods=["GET", "POST"])
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    posts_reversed_list = posts[::-1]

    generator_posts = database_api_data_to_render(posts_reversed_list)

    search = SearchForm()

    if current_user.is_authenticated:
        top_searches = render_top_searches(current_user.id)
    else:
        top_searches = None

    if search.validate_on_submit():
        add_new_search_item_to_general_db(search_name=search.search.data)

        if current_user.is_authenticated:
            add_new_search_item_to_db(search_name=search.search.data)
        return redirect(url_for("search_results", data=search.search.data))

    total_top_searches_result = render_general_top_searches()

    return render_template("index.html", all_posts=generator_posts, search=search,
                           top_searches=top_searches, total_top_searches_result=total_top_searches_result)


@app.route("/search/<data>", methods=["GET", "POST"])
def search_results(data):
    try:
        news = news_api(data)
        news_articles = news[:NUMS_OF_ARTICLES_TO_RENDER]
    except TypeError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        return render_template("search.html", news=news_articles, search_name_index=data.title())


@app.route("/<post_id>/page-2", methods=["GET", "POST"])
def new_api(post_id):
    try:
        news = news_api(post_id)
        news_articles = news[NUMS_OF_ARTICLES_TO_RENDER:]
    except TypeError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        return render_template("shownews.html", news=news_articles, search_name_index=post_id)


@app.route("/<post_id>/<post_search>")
def add_article_to_db(post_id, post_search):
    try:
        news = news_api(post_search)
    except TypeError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        for art in news:
            if art["title"] == post_id:
                with app.app_context():
                    new_blog = BlogPost(title=art["title"], subtitle=art["description"],
                                        author=current_user,
                                        img_url=art["urlToImage"], body=f"<a href='{art['url']}'>{art['url']}</a> "
                                                                        f"<b><--Goto URL, copy the body of the News "
                                                                        f"content, paste it in 'Edit Post' and summit"
                                                                        f"</b>",
                                        date=f"{date.today().strftime('%B')} {date.today().day}, {date.today().year}")
                    db.session.add(new_blog)
                    db.session.commit()
                return redirect(url_for("get_all_posts"))


def requested_blog_post(content):
    return jsonify(
        id=content.id,
        title=content.title,
        subtitle=content.subtitle,
        author=content.author.name,
        date=content.date,
        img_url=content.img_url,
        body=content.body
    ).json


def comments_on_post(comment_form, post_id):
    return jsonify(
        comment_posted=comment_form.comment.data,
        post_id=post_id
    ).json


def comments_on_post_api(comment_ins):
    for comment in comment_ins:
        yield jsonify(
            blog_post_id=comment.blog_post_id,
            comments_posted=comment.comments_posted,
            email=gravatar_url(email=comment.commenter.email),
            name=comment.commenter.name
        ).json


def gravatar_url(email, size=100, rating='g', default='retro', force_default=False):
    hash_value = md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_value}?s={size}&d={default}&r={rating}&f={force_default}"


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = requested_blog_post(db.get_or_404(BlogPost, post_id))

    comment = CommentsForm()

    comments = db.session.query(Comment)
    comments = comments[::-1]

    comments_json = comments_on_post_api(comments)

    ins_list = [com for com in comments if post_id == com.blog_post_id]
    number_of_comments = len(ins_list)

    if comment.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login or register an account with us to be able to comment")
            return redirect(url_for("register"))

        add_comments = comments_on_post(comment_form=comment, post_id=post_id)

        if len(add_comments["comment_posted"]) > 350:
            flash("Please keep your comment under 350 characters.")
        else:
            with app.app_context():

                new_comment = Comment(comments_posted=add_comments["comment_posted"], commenter=current_user,
                                      blog_post_id=add_comments["post_id"])
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for("show_post", post_id=post_id))

    return render_template("post.html", post=requested_post, form=comment, comments=comments_json,
                           count=number_of_comments)


def add_new_post_edit_post_internal_api(article_form):
    return jsonify(
        title=article_form.title.data,
        subtitle=article_form.subtitle.data,
        img_url=article_form.img_url.data,
        body=article_form.body.data,
        date=f"{date.today().strftime('%B')} {date.today().day}, {date.today().year}"
    ).json


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin
def add_new_post():
    blog_form = CreatePostForm()
    if blog_form.validate_on_submit():
        blog = add_new_post_edit_post_internal_api(blog_form)

        with app.app_context():
            new_blog = BlogPost(title=blog["title"], subtitle=blog["subtitle"],
                                author=current_user,
                                img_url=blog["img_url"], body=blog["body"],
                                date=blog["date"])
            db.session.add(new_blog)
            db.session.commit()

        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=blog_form)


def edit_post_internal_api(article_ins):
    return jsonify(
        title=article_ins.title,
        subtitle=article_ins.subtitle,
        img_url=article_ins.img_url,
        body=article_ins.body

    ).json


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin
def edit_post(post_id):
    ins_blog = db.get_or_404(BlogPost, post_id)
    ins_blog_json = edit_post_internal_api(ins_blog)

    blog_form = CreatePostForm()

    if blog_form.validate_on_submit():
        blog = add_new_post_edit_post_internal_api(blog_form)
        ins_blog.title = blog["title"]
        ins_blog.subtitle = blog["subtitle"]
        ins_blog.img_url = blog["img_url"]
        ins_blog.body = blog["body"]
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))

    blog_form.title.data = ins_blog_json["title"]
    blog_form.subtitle.data = ins_blog_json["subtitle"]
    blog_form.img_url.data = ins_blog_json["img_url"]
    blog_form.body.data = ins_blog_json["body"]
    return render_template("make-post.html", form=blog_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin
def delete_post_and_comments(post_id):
    comment = db.session.query(Comment)
    for blog_comments in comment:
        if post_id == blog_comments.blog_post_id:
            db.session.delete(blog_comments)
            db.session.commit()

    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


def send_message(name, email, phone, message) -> None:
    with smtplib.SMTP("smtp.gmail.com", SMTPLIB_CONNECT_NO) as connection:
        connection.starttls()
        connection.login(user='jeremylawrence112@gmail.com', password=os.getenv("PASSWORD"))
        connection.sendmail(from_addr='jeremylawrence112@gmail.com',
                            to_addrs='animitchel24@gmail.com',
                            msg=f"Subject:Mitchel's Blog!\n\n "
                                f"Name: {name}\n\n "
                                f"Email: {email}\n\n "
                                f"Phone: {phone}\n\n "
                                f"Message: {message.encode('utf-8')}")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        send_message(request.form.get('name'), request.form.get('email'), request.form.get('phone'),
                     request.form.get('message'))

        sent = True

        return render_template("contact.html", msg_sent=sent)
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
