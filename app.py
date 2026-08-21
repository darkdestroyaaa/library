import streamlit as st
import datetime
import seed_data
from heatmap import render_heatmap
from validation import check_availability
from commit import commit_copy
from rejection import explain_conflict
from suggestions import render_suggestions_panel
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="Contention Forecast", layout="wide")
st.title("📚 Library Book Contention Forecast")

# 1. Initialize session state (P5 / Infra)
if "books" not in st.session_state:
    st.session_state.books = seed_data.BOOKS

# 2. Book Selection & Heatmap Display (P1)
book_titles = [b["title"] for b in st.session_state.books]
selected_book = st.selectbox("Select a Book", book_titles)

if selected_book:
    st.subheader("Availability Heatmap (Next 14 Days)")
    render_heatmap(selected_book)

    st.markdown("---")
    st.subheader("Request to Borrow")

    # 3. Request Form (P2 / P3 / P4 / P5)
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.date(2026, 8, 4))
    with col2:
        end_date = st.date_input("End Date", datetime.date(2026, 8, 7))

    if st.button("Submit Request"):
        # Validate availability (P2)
        result = check_availability(selected_book, start_date, end_date)

        if result.get("success"):
            # Execute commit state write (P3)
            copy_id = result.get("copy_id")
            commit_copy(copy_id, start_date, end_date)
            st.success(f"Booking confirmed! Copy `{copy_id}` reserved from {start_date} to {end_date}.")
            st.rerun()
        else:
            # Display rejection explanation (P4)
            conflict_msg = explain_conflict(result)
            st.error(f"Request Rejected: {conflict_msg}")
            
            # Offer alternative date suggestions (P5)
            render_suggestions_panel(selected_book, start_date, end_date)