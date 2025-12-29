"""
記憶ページ
- 学習リスト管理
- 未学習/覚えたタブ切り替え
- 進捗表示
- 図解生成
"""
import streamlit as st
import streamlit.components.v1 as components
from config.settings import CATEGORIES, logger
from modules.learning_manager import (
    get_all_entries, get_unlearned, get_learned,
    get_progress_stats, mark_as_learned, mark_as_unlearned,
    remove_from_list
)
from modules.llm import generate_preview_svg

# ページ設定
st.set_page_config(page_title="記憶", page_icon="🧠", layout="wide")

logger.info("=== 記憶ページ表示 ===")

# セッション状態
if "memory_page" not in st.session_state:
    st.session_state.memory_page = {
        "generated_diagrams": {},  # {practice_id: svg}
        "expanded_items": set()    # 詳細展開中のID
    }

# 登録モード（グローバル）
if "learning_registration_mode" not in st.session_state:
    st.session_state.learning_registration_mode = False


def truncate_text(text: str, max_len: int = 100) -> str:
    """テキスト省略"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# ============================================================
# UI
# ============================================================

st.markdown("#### 🧠 記憶")

# 登録モードトグル
col_title, col_toggle = st.columns([3, 2])
with col_toggle:
    registration_mode = st.toggle(
        "📝 登録モード",
        value=st.session_state.learning_registration_mode,
        help="ONにすると検索ページでチェックボックスが表示されます"
    )
    if registration_mode != st.session_state.learning_registration_mode:
        st.session_state.learning_registration_mode = registration_mode
        st.rerun()

if st.session_state.learning_registration_mode:
    st.info("🔔 登録モードON: 検索ページの参考データにチェックボックスが表示されます")

st.markdown("---")

# 進捗表示
stats = get_progress_stats()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📚 合計", f"{stats['total']}件")
with col2:
    st.metric("📖 未学習", f"{stats['unlearned']}件")
with col3:
    st.metric("✅ 覚えた", f"{stats['learned']}件")
with col4:
    st.metric("📊 進捗", f"{stats['progress_percent']}%")

# プログレスバー
if stats["total"] > 0:
    st.progress(stats["progress_percent"] / 100)

st.markdown("---")

# タブ切り替え
tab_unlearned, tab_learned = st.tabs([
    f"📖 未学習 ({stats['unlearned']})",
    f"✅ 覚えた ({stats['learned']})"
])

# ------------------------------------------------------------
# 未学習タブ
# ------------------------------------------------------------
with tab_unlearned:
    unlearned_items = get_unlearned()

    if not unlearned_items:
        st.info("🎉 未学習の項目はありません！検索ページから学習リストに追加してください。")
    else:
        for item in unlearned_items:
            practice_id = item["practice_id"]
            category_label = CATEGORIES.get(item["category"], item["category"])

            with st.container():
                # ヘッダー行
                col1, col2, col3 = st.columns([0.6, 0.25, 0.15])

                with col1:
                    st.markdown(f"**{item['title']}**")
                    st.caption(f"🏷️ {category_label} | 追加: {item['added_at'][:10]}")

                with col2:
                    # 覚えたボタン
                    if st.button("✅ 覚えた", key=f"learn_{practice_id}", use_container_width=True):
                        mark_as_learned(practice_id)
                        st.rerun()

                with col3:
                    # 削除ボタン
                    if st.button("🗑️", key=f"del_{practice_id}"):
                        remove_from_list(practice_id)
                        st.rerun()

                # 説明文（省略表示）
                description = item.get("description", "")
                if description:
                    truncated = truncate_text(description, 100)
                    st.markdown(f"*{truncated}*")

                    # 詳細展開ボタン
                    if len(description) > 100:
                        if st.button("📄 詳細を見る", key=f"detail_{practice_id}"):
                            if practice_id in st.session_state.memory_page["expanded_items"]:
                                st.session_state.memory_page["expanded_items"].remove(practice_id)
                            else:
                                st.session_state.memory_page["expanded_items"].add(practice_id)
                            st.rerun()

                        if practice_id in st.session_state.memory_page["expanded_items"]:
                            st.markdown(description)

                # 図解生成ボタン
                if st.button("📐 図解生成", key=f"diagram_{practice_id}"):
                    with st.spinner("図解生成中..."):
                        svg = generate_preview_svg(description, item["title"])
                        st.session_state.memory_page["generated_diagrams"][practice_id] = svg

                # 図解表示
                if practice_id in st.session_state.memory_page["generated_diagrams"]:
                    svg = st.session_state.memory_page["generated_diagrams"][practice_id]
                    if svg.strip().startswith("<svg"):
                        components.html(f"""
                            <div style="background: white; padding: 10px; border-radius: 8px;">
                                {svg}
                            </div>
                        """, height=420)

                st.markdown("---")

# ------------------------------------------------------------
# 覚えたタブ
# ------------------------------------------------------------
with tab_learned:
    learned_items = get_learned()

    if not learned_items:
        st.info("まだ覚えた項目はありません。未学習タブで「覚えた」をクリックしてください。")
    else:
        for item in learned_items:
            practice_id = item["practice_id"]
            category_label = CATEGORIES.get(item["category"], item["category"])

            with st.container():
                col1, col2, col3 = st.columns([0.6, 0.25, 0.15])

                with col1:
                    st.markdown(f"~~**{item['title']}**~~")  # 打ち消し線
                    learned_date = item.get("learned_at", "")[:10] if item.get("learned_at") else ""
                    st.caption(f"🏷️ {category_label} | 習得: {learned_date}")

                with col2:
                    # 未学習に戻すボタン
                    if st.button("↩️ 未学習に戻す", key=f"unlearn_{practice_id}", use_container_width=True):
                        mark_as_unlearned(practice_id)
                        st.rerun()

                with col3:
                    # 削除ボタン
                    if st.button("🗑️", key=f"del_learned_{practice_id}"):
                        remove_from_list(practice_id)
                        st.rerun()

                st.markdown("---")

# デバッグ情報
with st.expander("🐛 デバッグ情報"):
    st.json(stats)
    st.write(f"図解キャッシュ: {len(st.session_state.memory_page['generated_diagrams'])}件")
