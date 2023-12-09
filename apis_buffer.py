from models import BlogPost, Comment, TopSearches, TotalTopSearches, User, db, app
from flask import jsonify
from flask_login import current_user
import requests
import os
from hashlib import md5
from datetime import date

TOP_SEARCH_NUMBER_RENDER = 5
INCREMENT = 1
DATA_ARTICLES_COUNT = 40


def news_api(search: str) -> list:
    """
    Fetches news articles related to the specified search query using the News API.

    Args:
        search (str): The search query to retrieve news articles.

    Returns:
        list: A list of news articles, each represented as a dictionary.

    Raises:
        requests.exceptions.HTTPError: If the HTTP request to the News API fails.
    """
    # Set the API key in the request header
    header = {
        "X-Api-Key": os.getenv("APIKEY")
    }

    # Set parameters for the News API request
    params = {
        "q": search,  # Search query
        "language": "en",  # Language of the articles (English)
        "sortBy": "publishedAt"  # Sort articles by publication date
    }

    # Make a GET request to the News API
    raw_data = requests.get(url="https://newsapi.org/v2/everything?", params=params, headers=header)

    # Raise an HTTPError if the request was unsuccessful
    raw_data.raise_for_status()

    # Parse the raw data as JSON
    data = raw_data.json()

    # Return a subset of articles (up to DATA_ARTICLES_COUNT)
    return data["articles"][:DATA_ARTICLES_COUNT]


def database_api_data_to_render(blog_post_list) -> list:
    """
    Convert a list of BlogPost objects to JSON data for rendering in an API response.

    Args:
        blog_post_list (list): List of BlogPost objects.

    Yields:
        dict: JSON data for each BlogPost object in the list.
    """
    for post in blog_post_list:
        # Yield JSON data for each BlogPost object
        yield jsonify(
            id=post.id,
            title=post.title,
            subtitle=post.subtitle,
            author=post.author.name,
            date=post.date
        ).json


def render_general_top_searches() -> list:
    """
    Render the top searches from the general database based on total search counts.

    Returns:
        list: A list of tuples containing total search count and search item, sorted by count in descending order.
    """
    # Query all entries from the TotalTopSearches table
    total_searches = db.session.query(TotalTopSearches)

    # Create a tuple of total search count and search item for each entry in the general database
    item_count_tuple = ((item.total_search_count, item.search_item) for item in total_searches)

    # Sort the list of tuples by total search count in descending order
    sorted_general_top_searches = sorted(list(item_count_tuple), reverse=True)

    # Return the top searches, limiting the result to the specified number
    return sorted_general_top_searches[:TOP_SEARCH_NUMBER_RENDER]


def add_new_search_item_to_general_db(search_name) -> None:
    """
    Add a new search item to the general database and update its total search count.

    Args:
        search_name (str): The search item to be added.

    Returns:
        None
    """
    # Convert the search name to a title case
    search_name = search_name.title()

    with app.app_context():
        # Check if the search item already exists in the general database
        total_top_searches = TotalTopSearches.query.filter_by(search_item=search_name).first()

        if total_top_searches:
            # If the search item exists, update its total search count and commit the changes
            db.get_or_404(TotalTopSearches, total_top_searches.id).total_search_count += INCREMENT
            db.session.commit()
            return

        # If the search item does not exist, create a new entry with an initial count
        search_json = jsonify(item=search_name, count=INCREMENT).json

        new_total_search_item = TotalTopSearches(search_item=search_json["item"],
                                                 total_search_count=search_json["count"])
        db.session.add(new_total_search_item)
        db.session.commit()


def render_top_searches(user_id) -> list:
    """
    Render the top searches for a given user based on search counts.

    Args:
        user_id (int): The ID of the user for whom to render top searches.

    Returns:
        list: A list of tuples containing search count and search item, sorted by count in descending order.
    """
    # Get the User object from the database using the provided user ID
    search_db = db.get_or_404(User, user_id)

    # Create a tuple of search count and search item for each top search in the user's database entry
    item_count_tuple = ((item.search_count, item.search_item) for item in search_db.top_search)

    # Sort the list of tuples by search count in descending order
    sorted_top_searches = sorted(list(item_count_tuple), reverse=True)

    # Return the top searches, limiting the result to the specified number
    return sorted_top_searches[:TOP_SEARCH_NUMBER_RENDER]


def add_new_search_item_to_db(search_name) -> None:
    # Convert the search_name to a title case for consistency
    search_name = search_name.title()

    # Use the app's app context to interact with the database
    with app.app_context():
        # Check if the search item already exists in the database
        top_searches = TopSearches.query.filter_by(search_item=search_name).first()

        if top_searches:
            # If the search item exists, increment the search count and update the database
            db.get_or_404(TopSearches, top_searches.id).search_count += INCREMENT
            db.session.commit()
            return

        # If the search item doesn't exist, create a new TopSearches entry
        search_json = jsonify(item=search_name, count=INCREMENT, user=current_user.id).json

        # Create a new TopSearches object with the search information
        new_searches_item = TopSearches(
            search_item=search_json["item"],
            search_count=search_json["count"],
            user_id=search_json["user"]
        )

        # Add the new entry to the database and commit the changes
        db.session.add(new_searches_item)
        db.session.commit()


def requested_blog_post(content):
    """
    Converts a blog post object into a JSON representation.

    Args:
        content (BlogPost): The blog post object to be converted.

    Returns:
        str: A JSON-formatted string representing the blog post.

    Note:
        This function uses the `jsonify` function to create a JSON response
        with specific attributes extracted from the provided `content` object.
    """

    # Use the jsonify function to create a JSON response.
    # The .json method is called to obtain the JSON-formatted string.
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
    """
    Creates a JSON representation of a comment and its associated post ID.

    Args:
        comment_form (CommentForm): An instance of the CommentForm class containing comment data.
        post_id (int): The unique identifier of the associated blog post.

    Returns:
        str: A JSON-formatted string representing the comment and post ID.
    """
    return jsonify(
        comment_posted=comment_form.comment.data,
        post_id=post_id
    ).json


def comments_on_post_api(comment_ins):
    """
    Generates JSON representations for a collection of comments.

    Args:
        comment_ins (iterable): An iterable containing Comment objects.

    Yields:
        str: JSON-formatted strings representing individual comments.
    """
    for comment in comment_ins:
        # Yield the JSON-formatted string for the current comment.
        yield jsonify(
            blog_post_id=comment.blog_post_id,
            comments_posted=comment.comments_posted,
            email=gravatar_url(email=comment.commenter.email),
            name=comment.commenter.name
        ).json


def add_new_post_edit_post_internal_api(article_form):
    """
    Converts the data from a blog post form to a JSON response.

    Args:
        article_form (FlaskForm): The form containing data for a new or edited blog post.

    Returns:
        str: The JSON response containing the blog post data.

    """
    # Create a JSON response with data from the blog post-form.
    return jsonify(
        title=article_form.title.data,
        subtitle=article_form.subtitle.data,
        img_url=article_form.img_url.data,
        body=article_form.body.data,
        date=f"{date.today().strftime('%B')} {date.today().day}, {date.today().year}"
    ).json


def edit_post_internal_api(article_ins):
    """
    Converts a BlogPost instance to a JSON response for internal API use.

    Args:
        article_ins (BlogPost): The BlogPost instance to be converted.

    Returns:
        dict: A dictionary representing the JSON response with title, subtitle, img_url, and body.

    """
    return jsonify(
        title=article_ins.title,
        subtitle=article_ins.subtitle,
        img_url=article_ins.img_url,
        body=article_ins.body
    ).json


def gravatar_url(email, size=100, rating='g', default='retro', force_default=False):
    """
    Generates a Gravatar URL based on the provided email address and optional parameters.

    Args:
        email (str): The email address associated with the Gravatar.
        size (int, optional): The desired size of the Gravatar image. Default is 100.
        rating (str, optional): The desired content rating ('g', 'pg', 'r', or 'x'). Default is 'g'.
        default (str, optional): The default image to use if no Gravatar is found. Default is 'retro'.
        force_default (bool, optional): Whether to force the default image to be used. Default is False.

    Returns:
        str: The URL for the Gravatar image.

    """
    # Calculate the MD5 hash of the lowercase email address.
    hash_value = md5(email.lower().encode('utf-8')).hexdigest()

    # Construct and return the Gravatar URL with the specified parameters.
    return f"https://www.gravatar.com/avatar/{hash_value}?s={size}&d={default}&r={rating}&f={force_default}"


def form_data(email, password, name=None):
    return jsonify(
        email=email,
        password=password,
        name=name
    ).json
