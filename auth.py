from typing import Optional, Tuple

import bcrypt
import streamlit as st

from models import create_user, get_user_by_username


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def register_new_user(username: str, password: str) -> Tuple[bool, str]:
    existing = get_user_by_username(username)
    if existing is not None:
        return False, "Kullanıcı adı zaten mevcut."

    password_hash = _hash_password(password)
    create_user(username=username, password_hash=password_hash)
    return True, "Kayıt başarılı. Artık giriş yapabilirsiniz."


def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[dict]]:
    user = get_user_by_username(username)
    if user is None:
        return False, None

    if not _verify_password(password, user["password_hash"]):
        return False, None

    return True, user


def login_user(user: dict) -> None:
    st.session_state["user_id"] = user["id"]
    st.session_state["username"] = user["username"]


def logout_user() -> None:
    for key in ("user_id", "username"):
        if key in st.session_state:
            del st.session_state[key]


def is_authenticated() -> bool:
    return "user_id" in st.session_state


def get_current_user() -> Optional[dict]:
    if not is_authenticated():
        return None
    return {
        "id": st.session_state.get("user_id"),
        "username": st.session_state.get("username"),
    }

