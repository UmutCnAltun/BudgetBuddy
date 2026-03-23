import streamlit as st


def page_title(title: str) -> None:
    st.title(title)

def show_info(message: str) -> None:
    st.info(message)


def show_success(message: str) -> None:
    st.success(message)


def show_error(message: str) -> None:
    st.error(message)

