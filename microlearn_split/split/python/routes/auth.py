from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required, logout_user

bp = Blueprint("auth", __name__)

# Registration and login are added in the next prompt.


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))
