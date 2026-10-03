from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/explore")
def explore():
    return render_template("explore.html")


@bp.route("/account")
@login_required
def account():
    return render_template("account.html")
