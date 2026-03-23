import streamlit as st

from auth import is_authenticated, get_current_user, logout_user
from ui.pages import (
    render_login_page,
    render_register_page,
    render_dashboard_page,
    render_settings_page,
    render_view_budgets_page,
    render_history_page,
    render_budget_detail_page,
)


PAGES_REQUIRING_AUTH = {
    "dashboard",
    "settings",
    "view_budgets",
    "history",
    "budget_detail",
}


def init_session_state() -> None:
    if "page" not in st.session_state:
        st.session_state["page"] = "login"
    if "selected_budget_id" not in st.session_state:
        st.session_state["selected_budget_id"] = None


def navigate_to(page: str) -> None:
    if page in PAGES_REQUIRING_AUTH and not is_authenticated():
        st.session_state["page"] = "login"
    else:
        st.session_state["page"] = page
    st.rerun()


def render_top_nav() -> None:
    st.image("images/logo.svg", width=140)

def main() -> None:
    st.set_page_config(page_title="BudgetBuddy", layout="wide")
    st.markdown(
        """
        <style>
        h1 a, h2 a, h3 a {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    init_session_state()

    view_param = st.query_params.get("view")
    if view_param in {"login", "register"}:
        st.session_state["page"] = view_param
    elif view_param:
        if is_authenticated():
            pass

    page = st.session_state.get("page", "login")

    if is_authenticated() and page == "login":
        page = "app"

    if page == "login":
        render_login_page(
            on_success=lambda: navigate_to("app"),
            on_switch_to_register=lambda: navigate_to("register"),
        )
    elif page == "register":
        render_register_page(
            on_success=lambda: navigate_to("login"),
            on_switch_to_login=lambda: navigate_to("login"),
        )
    else:
        if not is_authenticated():
            navigate_to("login")
            return

        render_top_nav()

        tab_dashboard, tab_expenses, tab_history, tab_settings = st.tabs(
            ["Kontrol Paneli", "Harcamalar", "Geçmiş", "Ayarlar"]
        )

        with tab_dashboard:
            render_dashboard_page()

        with tab_expenses:
            render_view_budgets_page()

        with tab_history:
            if st.session_state.get("history_view_detail"):
                render_budget_detail_page(
                    budget_id=st.session_state.get("selected_budget_id"),
                    on_back=lambda: (
                        st.session_state.pop("history_view_detail", None),
                        st.rerun(),
                    ),
                    key_prefix="history_",
                )
            else:
                render_history_page(
                    on_open_budget=lambda budget_id: (
                        st.session_state.__setitem__("selected_budget_id", budget_id),
                        st.session_state.__setitem__("history_view_detail", True),
                        st.rerun(),
                    )
                )

        with tab_settings:
            render_settings_page()
            st.subheader("Hesap")
            user = get_current_user()
            if user:
                st.write(f"Giriş Yapan: **{user['username']}**")
            
            st.write("")
            if st.button("Çıkış Yap", key="account_logout"):
                logout_user()
                navigate_to("login")


if __name__ == "__main__":
    main()

