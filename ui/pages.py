from typing import Callable, Optional

import datetime as dt
import pandas as pd
import streamlit as st
import altair as alt
from streamlit_echarts import st_echarts

from auth import authenticate_user, login_user, register_new_user
from models import (
    create_budget,
    create_transaction,
    delete_transaction,
    get_budget_by_id,
    get_budget_summary_and_frame,
    list_budgets_for_user,
    update_budget,
    update_transaction,
    ensure_current_budget_for_user,
)
from ui.layout import page_title, show_error, show_success


def render_login_page(
    *,
    on_success: Callable[[], None],
    on_switch_to_register: Callable[[], None],
) -> None:
    st.image("images/logo.svg", width=140)
    st.markdown("---")
    page_title("Giriş Yap")

    with st.form("login_form"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")

        submitted = st.form_submit_button(
            "Giriş Yap",
            width="stretch",
        )

        if submitted:
            ok, user = authenticate_user(username, password)
            if ok and user is not None:
                login_user(user)
                show_success("Başarıyla giriş yapıldı.")
                on_success()
            else:
                show_error("Geçersiz kullanıcı adı veya şifre.")

    col_text, col_link = st.columns([3, 1])
    with col_text:
        st.markdown("Hesabınız yok mu?")
    with col_link:
        if st.button("**Kayıt Ol**", key="auth_login_to_register", width="stretch"):
            on_switch_to_register()


def render_register_page(
    *,
    on_success: Callable[[], None],
    on_switch_to_login: Callable[[], None],
) -> None:
    page_title("Kayıt Ol")

    with st.form("register_form"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        confirm_password = st.text_input("Şifreyi Onayla", type="password")

        submitted = st.form_submit_button(
            "Hesap Oluştur",
            width="stretch",
        )

        if submitted:
            if not username or not password:
                show_error("Kullanıcı adı ve şifre zorunludur.")
            elif password != confirm_password:
                show_error("Şifreler eşleşmiyor.")
            else:
                ok, msg = register_new_user(username, password)
                if ok:
                    show_success(msg)
                    on_success()
                else:
                    show_error(msg)

    col_text, col_link = st.columns([3, 1])
    with col_text:
        st.markdown("Zaten bir hesabınız var mı?")
    with col_link:
        if st.button("**Giriş Yap**", key="auth_register_to_login", width="stretch"):
            on_switch_to_login()


def find_budget_for_date(user_id: int, date_val: dt.date) -> Optional[dict[str, any]]:
    """Helper to find which budget period a date belongs to."""
    budgets = list_budgets_for_user(user_id)
    for b in budgets:
        if b.get("start_date") and b.get("end_date"):
            try:
                start = dt.date.fromisoformat(b["start_date"])
                end = dt.date.fromisoformat(b["end_date"])
                if start <= date_val <= end:
                    return b
            except ValueError:
                continue
    return None


def _require_user_id() -> Optional[int]:
    user_id = st.session_state.get("user_id")
    if user_id is None:
        show_error("Bu sayfayı görüntülemek için giriş yapmalısınız.")
    return user_id


def render_dashboard_page() -> None:
    page_title("Kontrol Paneli")
    user_id = _require_user_id()
    if user_id is None:
        return

    ensure_current_budget_for_user(user_id)
    budgets = list_budgets_for_user(user_id)
    if not budgets:
        st.caption("Henüz bütçe yok. İlk bütçenizi oluşturmak için **Ayarlar** sayfasına gidin.")
        return

    today = dt.date.today()
    current_budget = None
    for b in budgets:
        end = None
        if b.get("end_date"):
            try:
                end = dt.date.fromisoformat(b["end_date"])
            except ValueError:
                end = None
        if end is None or end >= today:
            current_budget = b
            break
    if current_budget is None:
        current_budget = budgets[0]

    summary, df = get_budget_summary_and_frame(
        budget_id=current_budget["id"],
        total_amount=float(current_budget["total_amount"]),
    )

    currency_symbol_map = {"TRY": "₺", "USD": "$", "EUR": "€", "GBP": "£"}
    currency_code = current_budget.get("currency", "TRY")
    symbol = currency_symbol_map.get(currency_code, "₺")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gelir", f"{symbol}{summary['total_income']:.2f}")
    col2.metric("Giderler", f"{symbol}{summary['total_expenses']:.2f}")
    col3.metric("Kalan", f"{symbol}{summary['remaining']:.2f}")
    col4.metric("Kullanılan %", f"{summary['percentage_used']:.1f}%")

    st.markdown("---")
    
    st.subheader("İşlem Ekle")
    
    default_categories = [
        "Market", "Dışarıda Yemek", "Kira/Konut Kredisi", "Faturalar", 
        "Ulaşım", "Eğlence", "Sağlık", "Alışveriş", 
        "Kişisel Bakım", "Eğitim", "Seyahat", "Tasarruf/Yatırım", "Özel"
    ]

    with st.form("dashboard_add_transaction_form", clear_on_submit=True):
        col_input1, col_input2 = st.columns(2)
        with col_input1:
            amount = st.number_input("Tutar", min_value=0.0, step=10.0)
            date_val = st.date_input("Tarih", value=dt.date.today())
            type_ = st.selectbox(
                "Tür",
                ["Expense", "Income"],
                format_func=lambda x: "Gider" if x == "Expense" else "Gelir",
            )
        
        with col_input2:
            cat_select = st.selectbox("Kategori", default_categories)
            cat_custom = st.text_input("Özel Kategori Adı", help="'Özel' seçiliyse zorunludur")
            description = st.text_input("Açıklama")

        submitted = st.form_submit_button("İşlem Ekle", width="stretch")
    
    if submitted:
        final_category = cat_select
        if cat_select == "Özel":
            final_category = cat_custom
        
        if amount <= 0:
            show_error("Tutar sıfırdan büyük olmalıdır.")
        elif not final_category:
            show_error("Kategori zorunludur.")
        else:
            target_budget = find_budget_for_date(user_id, date_val)
            if target_budget is None:
                target_budget = current_budget
            
            type_lower = type_.lower()
            
            if type_lower == "income":
                new_total = float(target_budget["total_amount"]) + float(amount)
                update_budget(
                    budget_id=target_budget["id"],
                    name=target_budget["name"],
                    total_amount=new_total,
                    start_date=target_budget["start_date"],
                    end_date=target_budget["end_date"],
                    frequency=target_budget["frequency"],
                    currency=target_budget.get("currency", "TRY"),
                )

            create_transaction(
                budget_id=target_budget["id"],
                amount=float(amount),
                date=date_val.isoformat() if date_val else dt.date.today().isoformat(),
                category=final_category,
                description=description,
                type_=type_lower,
            )
            
            if target_budget["id"] == current_budget["id"]:
                show_success("İşlem eklendi.")
            else:
                show_success(f"İşlem şu bütçe dönemine eklendi: {target_budget['start_date']} - {target_budget['end_date']}")
            st.rerun()

    st.subheader("Harcama Özeti")
    if not df.empty:
        expense_df = df[df["type"] == "expense"]
        if not expense_df.empty:
            cat_group = (
                expense_df.groupby("category")["amount"]
                .sum()
                .reset_index()
                .sort_values("amount", ascending=False)
            )

            remaining_val = max(0.0, summary["remaining"])
            if remaining_val > 0:
                new_row = pd.DataFrame([{"category": "Kalan", "amount": remaining_val}])
                cat_group = pd.concat([cat_group, new_row], ignore_index=True)
            
            st.caption("Kategoriye Göre Harcama Grafiği (Çubuk)")
            bar_chart = alt.Chart(cat_group).mark_bar().encode(
                x=alt.X("category", sort="-y", title="Kategori"),
                y=alt.Y("amount", title="Tutar"),
                color=alt.Color("category", title="Kategori"),
                tooltip=[
                    alt.Tooltip("category", title="Kategori"),
                    alt.Tooltip("amount", format=".2f", title=f"Tutar ({symbol})")
                ]
            )
            st.altair_chart(bar_chart, width="stretch")
            
            st.caption("Kategoriye Göre Harcama Grafiği (Pasta)")
            base = alt.Chart(cat_group).encode(
                theta=alt.Theta("amount", stack=True)
            )
            pie = base.mark_arc(outerRadius=130).encode(
                color=alt.Color("category", title="Kategori"),
                order=alt.Order("amount", sort="descending"),
                tooltip=[
                    alt.Tooltip("category", title="Kategori"), 
                    alt.Tooltip("amount", format=".2f", title=f"Tutar ({symbol})")
                ]
            )
            text = base.mark_text(radius=140).encode(
                text="category",
                order=alt.Order("amount", sort="descending"),
                color=alt.value("white")
            )
            st.altair_chart(pie + text, width="stretch")

            st.caption("Günlük Harcama Eğilimi Grafiği (Bu Hafta)")

            trend_df = expense_df.copy()
            trend_df["date_dt"] = pd.to_datetime(trend_df["date"])

            today = dt.date.today()
            start_week = today - dt.timedelta(days=today.weekday())
            end_week = start_week + dt.timedelta(days=6)

            mask = (trend_df["date_dt"].dt.date >= start_week) & (
                trend_df["date_dt"].dt.date <= end_week
            )
            this_week_df = trend_df.loc[mask]
            daily_sums = (
                this_week_df.groupby(this_week_df["date_dt"].dt.weekday)["amount"].sum()
            )

            daily_sums = daily_sums.reindex(range(7), fill_value=0.0)

            data_values = [round(x, 2) for x in daily_sums.tolist()]

            option = {
                "xAxis": {
                    "type": "category",
                    "data": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
                },
                "yAxis": {"type": "value"},
                "series": [{"data": data_values, "type": "line"}],
                "tooltip": {"trigger": "axis"},
            }
            st_echarts(options=option, height="400px", key="dashboard_spending_trend")
        else:
            st.caption("Görüntülenecek gider işlemi yok.")
    else:
        st.caption("Henüz hiç işlem yok.")
    
    

def render_settings_page() -> None:
    user_id = _require_user_id()
    if user_id is None:
        return

    page_title("Ayarlar")
    ensure_current_budget_for_user(user_id)
    budgets = list_budgets_for_user(user_id)
    existing_budget = budgets[0] if budgets else None

    st.subheader("Bütçe Detayları")

    if not budgets:
        st.caption("Paranızı takip etmeye başlamak için bir bütçe oluşturun.")
    else:
        st.caption("")
    freq_label_to_value = {"Weekly": "weekly", "Monthly": "monthly"}
    existing_freq_value = (
        existing_budget.get("frequency") if existing_budget else "monthly"
    )
    existing_label = next(
        (label for label, val in freq_label_to_value.items() if val == existing_freq_value),
        "Monthly",
    )
    labels = list(freq_label_to_value.keys())
    default_index = labels.index(existing_label)

    currency_options = {
        "TRY": "Türk Lirası (₺)",
        "USD": "ABD Doları ($)",
        "EUR": "Euro (€)",
        "GBP": "İngiliz Sterlini (£)",
    }
    existing_currency = (
        existing_budget.get("currency") if existing_budget else "TRY"
    )
    if existing_currency not in currency_options:
        existing_currency = "TRY"
        
    currency_keys = list(currency_options.keys())
    currency_index = currency_keys.index(existing_currency)

    with st.form("budget_settings_form"):
        total_amount = st.number_input(
            "Toplam Bütçe",
            min_value=0.0,
            step=100.0,
            value=float(existing_budget["total_amount"]) if existing_budget else 0.0,
        )
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Başlangıç Tarihi",
                value=None
                if not existing_budget or not existing_budget["start_date"]
                else existing_budget["start_date"],
            )
        with col2:
            freq_label = st.selectbox(
                "Bütçe Döngüsü",
                labels,
                index=default_index,
                format_func=lambda x: "Haftalık" if x == "Weekly" else "Aylık",
            )

        currency_code = st.selectbox(
            "Para Birimi", 
            currency_keys, 
            format_func=lambda x: currency_options[x],
            index=currency_index
        )

        submitted = st.form_submit_button(
            "Bütçeyi Kaydet" if existing_budget else "Bütçe Oluştur",
            width="stretch",
        )

    if submitted:
        frequency_value = freq_label_to_value[freq_label]
        
        start_str = start_date.isoformat() if start_date else None
        end_str = None
        if start_date:
            if frequency_value == "weekly":
                computed_end = start_date + dt.timedelta(days=6)
            else:
                computed_end = start_date + dt.timedelta(days=29)
            end_str = computed_end.isoformat()

        if existing_budget:
            update_budget(
                budget_id=existing_budget["id"],
                name=existing_budget["name"],
                total_amount=float(total_amount),
                start_date=start_str,
                end_date=end_str,
                frequency=frequency_value,
                currency=currency_code,
            )
            show_success("Bütçe güncellendi.")
            st.rerun()
        else:
            create_budget(
                user_id=user_id,
                name="Bütçem",
                total_amount=float(total_amount),
                start_date=start_str,
                end_date=end_str,
                frequency=frequency_value,
                currency=currency_code,
            )
            show_success("Bütçe oluşturuldu.")
            st.rerun()


def render_view_budgets_page() -> None:
    page_title("Giderler")
    user_id = _require_user_id()
    if user_id is None:
        return

    ensure_current_budget_for_user(user_id)

    budgets = list_budgets_for_user(user_id)
    if not budgets:
        st.caption("Henüz bir bütçe yok. Oluşturmak için **Ayarlar** sayfasına gidin.")
        return

    today = dt.date.today()
    current_budget = None
    for b in budgets:
        end = None
        if b.get("end_date"):
            try:
                end = dt.date.fromisoformat(b["end_date"])
            except ValueError:
                end = None
        if end is None or end >= today:
            current_budget = b
            break

    if current_budget is None:
        current_budget = budgets[0]

    render_budget_detail_page(budget_id=current_budget["id"], on_back=None, key_prefix="expenses_")


def render_history_page(
    *,
    on_open_budget: Callable[[int], None],
) -> None:
    page_title("Geçmiş")
    user_id = _require_user_id()
    if user_id is None:
        return
    ensure_current_budget_for_user(user_id)

    budgets = list_budgets_for_user(user_id)
    if not budgets:
        st.caption("Henüz geçmiş bütçe yok. Zamanla yeni bütçeler oluşturdukça, eski olanlar burada görünecek.")
        return

    today = dt.date.today()
    past_budgets = []
    for b in budgets:
        end = None
        if b.get("end_date"):
            try:
                end = dt.date.fromisoformat(b["end_date"])
            except ValueError:
                end = None
        if end is not None and end < today:
            past_budgets.append(b)

    if not past_budgets:
        st.caption("Henüz geçmiş bütçe yok. Mevcut bütçe döneminiz bittiğinde, otomatik olarak buraya taşınacaktır.")
        return

    for b in past_budgets:
        summary, _ = get_budget_summary_and_frame(
            budget_id=b["id"], total_amount=float(b["total_amount"])
        )
        with st.container():
            st.write(f"Dönem: {b.get('start_date') or ''} – {b.get('end_date') or ''}")
            cols = st.columns(4)
            cols[0].metric("Bütçelenen", f"{float(b['total_amount']):.2f}")
            cols[1].metric("Gelir", f"{summary['total_income']:.2f}")
            cols[2].metric("Giderler", f"{summary['total_expenses']:.2f}")
            cols[3].metric("Kalan", f"{summary['remaining']:.2f}")

            if st.button(f"Detayları Görüntüle", key=f"history_view_{b['id']}"):
                on_open_budget(b["id"])


def render_budget_detail_page(
    *, budget_id: int, on_back: Optional[Callable[[], None]] = None, key_prefix: str = ""
) -> None:
    user_id = _require_user_id()
    if user_id is None:
        return

    if on_back:
        if st.button("← Geri", key=f"{key_prefix}top_back_btn"):
            on_back()
            st.rerun()

    if budget_id is None:
        show_error("Herhangi bir bütçe seçilmedi.")
        return

    budget = get_budget_by_id(budget_id)
    if budget is None or budget["user_id"] != user_id:
        show_error("Bütçe bulunamadı.")
        return

    summary, df = get_budget_summary_and_frame(
        budget_id=budget["id"], total_amount=float(budget["total_amount"])
    )

    currency_symbol_map = {"TRY": "₺", "USD": "$", "EUR": "€", "GBP": "£"}
    currency_code = budget.get("currency", "TRY")
    symbol = currency_symbol_map.get(currency_code, "₺")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Toplam Bütçe", f"{symbol}{float(budget['total_amount']):.2f}")
    col2.metric("Eklenen Gelir", f"{symbol}{summary.get('added_income', 0.0):.2f}")
    col3.metric("Giderler", f"{symbol}{summary['total_expenses']:.2f}")
    col4.metric("Kalan", f"{symbol}{summary['remaining']:.2f}")

    st.subheader("İşlem Ekle")
    
    default_categories = [
        "Market", "Dışarıda Yemek", "Kira/Konut Kredisi", "Faturalar", 
        "Ulaşım", "Eğlence", "Sağlık", "Alışveriş", 
        "Kişisel Bakım", "Eğitim", "Seyahat", "Tasarruf/Yatırım", "Özel"
    ]

    with st.form(f"{key_prefix}add_transaction_form", clear_on_submit=True):
        amount = st.number_input("Tutar", min_value=0.0, step=10.0, key=f"{key_prefix}add_tx_amount")
        date_val = st.date_input("Tarih", value=dt.date.today(), key=f"{key_prefix}add_tx_date")
        
        cat_select = st.selectbox("Kategori", default_categories, key=f"{key_prefix}add_tx_category")
        cat_custom = st.text_input("Özel Kategori Adı", help="'Özel' seçiliyse zorunludur", key=f"{key_prefix}add_tx_cat_custom")
        
        description = st.text_input("Açıklama", key=f"{key_prefix}add_tx_description")
        type_ = st.selectbox(
            "Tür",
            ["Expense", "Income"],
            key=f"{key_prefix}add_tx_type",
            format_func=lambda x: "Gider" if x == "Expense" else "Gelir",
        )

        submitted = st.form_submit_button("İşlem Ekle", width="stretch")
    
    if submitted:
        final_category = cat_select
        if cat_select == "Özel":
            final_category = cat_custom
        
        if amount <= 0:
            show_error("Tutar sıfırdan büyük olmalıdır.")
        elif not final_category:
            show_error("Kategori zorunludur.")
        else:
            target_budget = find_budget_for_date(user_id, date_val)
            if target_budget is None:
                target_budget = budget
            
            type_lower = type_.lower()
            
            if type_lower == "income":
                new_total = float(target_budget["total_amount"]) + float(amount)
                update_budget(
                    budget_id=target_budget["id"],
                    name=target_budget["name"],
                    total_amount=new_total,
                    start_date=target_budget["start_date"],
                    end_date=target_budget["end_date"],
                    frequency=target_budget["frequency"],
                    currency=target_budget.get("currency", "TRY"),
                )

            create_transaction(
                budget_id=target_budget["id"],
                amount=float(amount),
                date=date_val.isoformat() if date_val else dt.date.today().isoformat(),
                category=final_category,
                description=description,
                type_=type_lower,
            )
            
            if target_budget["id"] == budget["id"]:
                show_success("İşlem eklendi.")
            else:
                show_success(f"İşlem şu döneme eklendi: {target_budget['start_date']} - {target_budget['end_date']}")
            st.rerun()

    st.subheader("İşlemler")
    if df.empty:
        st.caption("Henüz hiç işlem yok.")
    else:
        for _, row in df.iterrows():
            with st.expander(
                f"{row['date']} - "
                f"{'Gelir' if row['type'] == 'income' else 'Gider'} - "
                f"{row['category']} - {row['amount']:.2f}"
            ):
                st.write(f"Açıklama: {row.get('description') or ''}")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Sil", key=f"{key_prefix}delete_tx_{row['id']}"):
                        delete_transaction(int(row["id"]))
                        show_success("İşlem silindi.")
                        st.rerun()
                with col_b:
                    if st.button("Düzenle", key=f"{key_prefix}edit_tx_{row['id']}"):
                        st.session_state["edit_tx_id"] = int(row["id"])
                        st.rerun()

        edit_tx_id = st.session_state.get("edit_tx_id")
        if edit_tx_id is not None:
            edit_row = df.loc[df["id"] == edit_tx_id]
            if not edit_row.empty:
                r = edit_row.iloc[0]
                st.subheader("İşlemi Düzenle")
                
                edit_categories = [
                    "Market", "Dışarıda Yemek", "Kira/Konut Kredisi", "Faturalar", 
                    "Ulaşım", "Eğlence", "Sağlık", "Alışveriş", 
                    "Kişisel Bakım", "Eğitim", "Seyahat", "Tasarruf/Yatırım", "Özel"
                ]
                current_cat = r.get("category") or ""
                if current_cat in edit_categories:
                    cat_index = edit_categories.index(current_cat)
                    custom_val = ""
                else:
                    cat_index = edit_categories.index("Özel")
                    custom_val = current_cat

                with st.form(f"{key_prefix}edit_tx_form_{r['id']}"):
                    tx_id = r["id"]
                    
                    type_edit = st.selectbox(
                        "Tür", ["Expense", "Income"], 
                        index=0 if r["type"] == "expense" else 1,
                        key=f"{key_prefix}edit_tx_type_{tx_id}",
                        format_func=lambda x: "Gider" if x == "Expense" else "Gelir",
                    )
                    
                    cat_select_edit = st.selectbox(
                        "Kategori", edit_categories, 
                        index=cat_index,
                        key=f"{key_prefix}edit_tx_category_{tx_id}"
                    )
                    
                    cat_custom_edit = st.text_input(
                        "Özel Kategori Adı ('Özel' seçiliyse)", 
                        value=custom_val,
                        key=f"{key_prefix}edit_tx_cat_custom_{tx_id}"
                    )
                    
                    amount_edit = st.number_input(
                        "Tutar", min_value=0.0, step=10.0, 
                        value=float(r["amount"]),
                        key=f"{key_prefix}edit_tx_amount_{tx_id}"
                    )
                    description_edit = st.text_input(
                        "Açıklama", 
                        value=r.get("description") or "",
                        key=f"{key_prefix}edit_tx_description_{tx_id}"
                    )
                    date_edit = st.date_input(
                        "Tarih",
                        value=None if not r.get("date") else r["date"],
                        key=f"{key_prefix}edit_tx_date_{tx_id}"
                    )
                    
                    if st.form_submit_button("Değişiklikleri Kaydet", key=f"{key_prefix}edit_tx_submit_{tx_id}"):
                        final_cat_edit = cat_select_edit
                        if cat_select_edit == "Özel":
                            final_cat_edit = cat_custom_edit
                        
                        if not final_cat_edit:
                            show_error("Kategori zorunludur.")
                        else:
                            update_transaction(
                                transaction_id=int(r["id"]),
                                type_=type_edit,
                                category=final_cat_edit,
                                amount=float(amount_edit),
                                description=description_edit,
                                date=date_edit.isoformat() if date_edit else None,
                            )
                            show_success("İşlem güncellendi.")
                            st.session_state["edit_tx_id"] = None
                            st.rerun()

    st.subheader("Harcama Özeti")
    if not df.empty:
        expense_df = df[df["type"] == "expense"]
        if not expense_df.empty:
            cat_group = (
                expense_df.groupby("category")["amount"]
                .sum()
                .reset_index()
                .sort_values("amount", ascending=False)
            )
            remaining_val = max(0.0, summary["remaining"])
            if remaining_val > 0:
                new_row = pd.DataFrame([{"category": "Kalan", "amount": remaining_val}])
                cat_group = pd.concat([cat_group, new_row], ignore_index=True)
            
            st.caption("Kategoriye Göre Harcama Grafiği (Çubuk)")
            bar_chart = alt.Chart(cat_group).mark_bar().encode(
                x=alt.X("category", sort="-y", title="Kategori"),
                y=alt.Y("amount", title="Tutar"),
                color=alt.Color("category", title="Kategori"),
                tooltip=[
                    alt.Tooltip("category", title="Kategori"),
                    alt.Tooltip("amount", format=".2f", title=f"Tutar ({symbol})")
                ]
            )
            st.altair_chart(bar_chart, key=f"{key_prefix}bar_chart", width="stretch")

            st.caption("Kategoriye Göre Harcama Grafiği (Pasta)")
            base = alt.Chart(cat_group).encode(
                theta=alt.Theta("amount", stack=True)
            )
            pie = base.mark_arc(outerRadius=130).encode(
                color=alt.Color("category", title="Kategori"),
                order=alt.Order("amount", sort="descending"),
                tooltip=[
                    alt.Tooltip("category", title="Kategori"), 
                    alt.Tooltip("amount", format=".2f", title=f"Tutar ({symbol})")
                ]
            )
            text = base.mark_text(radius=140).encode(
                text="category",
                order=alt.Order("amount", sort="descending"),
                color=alt.value("white")
            )
            st.altair_chart(pie + text, key=f"{key_prefix}pie_chart", width="stretch")

            trend_df = expense_df.copy()
            trend_df["date_dt"] = pd.to_datetime(trend_df["date"])

            today = dt.date.today()
            start_week = today - dt.timedelta(days=today.weekday())
            end_week = start_week + dt.timedelta(days=6)

            mask = (trend_df["date_dt"].dt.date >= start_week) & (
                trend_df["date_dt"].dt.date <= end_week
            )
            this_week_df = trend_df.loc[mask]

            daily_sums = (
                this_week_df.groupby(this_week_df["date_dt"].dt.weekday)["amount"].sum()
            )
            daily_sums = daily_sums.reindex(range(7), fill_value=0.0)

            data_values = [round(x, 2) for x in daily_sums.tolist()]

            option = {
                "xAxis": {
                    "type": "category",
                    "data": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
                },
                "yAxis": {"type": "value"},
                "series": [{"data": data_values, "type": "line"}],
                "tooltip": {"trigger": "axis"},
            }
            st_echarts(options=option, height="400px", key=f"{key_prefix}spending_trend")
        else:
            st.caption("Görüntülenecek gider işlemi yok.")
    else:
        st.caption("Görüntülenecek işlem yok.")