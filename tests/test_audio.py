import io

import pytest

from backend.audio import MAX_AUDIO_BYTES, check_audio

WAV = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"fmt " + b"\x00" * 20
MP3 = b"ID3" + b"\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 100


def signup_company(client, email="hr@acme.md"):
    return client.post("/signup", data={
        "type": "company", "company_name": "Acme", "email": email,
    }, follow_redirects=True)


def upload(client, data=MP3, name="song.mp3"):
    return client.post(
        "/audio/upload",
        data={"audio": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
    )


# --- проверка файла (без Flask) -------------------------------------------

def test_accepts_mp3_and_wav():
    assert check_audio("a.mp3", MP3) == "audio/mpeg"
    assert check_audio("A.WAV", WAV) == "audio/wav"


@pytest.mark.parametrize("name, data", [
    ("a.ogg", MP3),                 # неподдерживаемый формат
    ("a.mp3", b""),                 # пустой файл
    ("a.mp3", b"not audio at all"), # расширение mp3, но внутри не mp3
    ("a.wav", MP3),                 # mp3 под видом wav
    ("noext", MP3),
])
def test_rejects_bad_files(name, data):
    with pytest.raises(ValueError):
        check_audio(name, data)


def test_rejects_too_large():
    with pytest.raises(ValueError):
        check_audio("a.wav", WAV + b"\x00" * MAX_AUDIO_BYTES)


# --- маршруты --------------------------------------------------------------

def test_upload_requires_login(client):
    response = upload(client)
    assert response.status_code in (302, 401)


def test_upload_and_get_back_same_bytes(client):
    signup_company(client)
    response = upload(client)
    assert response.status_code == 201

    got = client.get(response.get_json()["url"])
    assert got.status_code == 200
    assert got.mimetype == "audio/mpeg"
    assert got.data == MP3


def test_upload_wav(client):
    signup_company(client)
    response = upload(client, WAV, "voice.wav")
    assert response.status_code == 201
    assert client.get(response.get_json()["url"]).data == WAV


def test_upload_rejects_wrong_format(client):
    signup_company(client)
    response = upload(client, b"hello", "notes.txt")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_standalone_audio_is_private_to_uploader(app, client):
    signup_company(client)
    url = upload(client).get_json()["url"]

    stranger = app.test_client()
    assert stranger.get(url).status_code == 403