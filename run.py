from core import create_app  # also loads .env

app = create_app()

if __name__ == "__main__":
    import os

    # HOST=0.0.0.0 in .env lets other devices in the same Wi-Fi open the site.
    # By default only this computer can (127.0.0.1).
    app.run(debug=True, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 5000)))