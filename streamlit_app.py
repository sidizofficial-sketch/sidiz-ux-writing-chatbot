import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pandas as pd

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="시디즈 UX 라이팅 가이드",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. CSS 스타일 추가 (복사 버튼 - 항상 표시)
# ==========================================
st.markdown("""
<style>
.response-container {
    position: relative;
    padding-right: 40px;
}

.copy-button {
    position: absolute;
    right: 0;
    top: 0;
    background: transparent;
    border: none;
    cursor: pointer;
    opacity: 0.5;
    transition: opacity 0.2s;
    font-size: 20px;
    padding: 5px;
}

.copy-button:hover {
    opacity: 1;
}

.source-link {
    color: #0066cc;
    text-decoration: none;
}

.source-link:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. Google Sheets 설정
# ==========================================
def get_gsheet_client():
    """Google Sheets 클라이언트 초기화"""
    try:
        if "gcp_service_account" not in st.secrets:
            return None
            
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.sidebar.warning(f"⚠️ Google Sheets 연동 안됨")
        return None

def save_feedback_to_sheet(original_text, converted_text, feedback, mode, reason="", comment=""):
    """피드백을 Google Sheets에 저장"""
    try:
        client = get_gsheet_client()
        if client is None:
            return False
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            return False
        
        sheet = client.open_by_url(sheet_url).sheet1
        
        if sheet.row_count == 0 or sheet.cell(1, 1).value != "시간":
            sheet.insert_row(["시간", "모드", "원본 문구", "변환된 문구", "피드백", "피드백값", "싫어요 사유", "코멘트"], 1)
        
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode,
            original_text,
            converted_text,
            "👍" if feedback == 1 else "👎",
            feedback,
            reason,
            comment
        ]
        
        sheet.append_row(row)
        return True
        
    except Exception as e:
        return False

def load_negative_feedback():
    """부정 피드백 로드"""
    try:
        client = get_gsheet_client()
        if client is None:
            return ""
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            return ""
        
        sheet = client.open_by_url(sheet_url).sheet1
        records = sheet.get_all_records()
        
        if not records:
            return ""
        
        df = pd.DataFrame(records)
        negative_df = df[df['피드백값'] == 0]
        
        if negative_df.empty:
            return ""
        
        negative_examples = ""
        for _, row in negative_df.tail(10).iterrows():
            negative_examples += f"""
원본: "{row['원본 문구']}"
나쁜 변환: "{row['변환된 문구']}" 
사유: {row.get('싫어요 사유', 'N/A')}
코멘트: {row.get('코멘트', 'N/A')}
← 이런 스타일 절대 피하기
"""
        
        return f"""
[사용자가 싫어한 변환 스타일 - 절대 사용 금지]
{negative_examples}
"""
        
    except Exception as e:
        return ""

# ==========================================
# 4. Gemini API 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
except KeyError as e:
    st.error(f"❌ Secrets 설정 오류: {e}")
    st.stop()

# ==========================================
# 5. 모델 초기화
# ==========================================
@st.cache_resource
def get_gemini_model():
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    return genai.GenerativeModel(target)

# ==========================================
# 6. 프롬프트 생성 함수
# ==========================================
def generate_prompt(mode, user_input, negative_feedback):
    """모드별 프롬프트 생성"""
    
    base_instruction = f"""
너는 시디즈의 전문 UX 라이터야. 사용자가 입력한 일반 문구를 시디즈만의 브랜드 보이스로 변환해줘.

[시디즈 브랜드 보이스 핵심]
- 전문적이면서도 따뜻한 조력자
- 사용자 중심의 세심한 배려
- 혁신과 지속가능성에 대한 진정성

{negative_feedback}
"""
    
    if mode == "UX":
        mode_instruction = """
[UX 모드 - 브랜드 감성 & 친절한 조력자]

변환 시 다음에 집중하세요:
1. 감성적 연결: 사용자의 감정과 니즈에 공감하는 표현
2. 친절한 안내: 전문적이되 따뜻하고 접근하기 쉬운 톤
3. 경험 중심: 제품의 스펙보다 사용자가 느낄 경험을 강조
4. 신뢰감: 과장 없이 진솔하고 믿을 수 있는 표현

변환 예시:
원본: "편안한 의자"
변환: "하루 종일 앉아 있어도 지치지 않도록, 당신의 몸을 세심하게 배려한 시팅 경험을 제공합니다"

중요: 출처 URL은 포함하지 마세요.
"""
    
    else:
        mode_instruction = """
[SEO/GEO 모드 - 검색 최적화 + 증거 기반]

변환 시 다음을 모두 포함하세요:
1. 핵심 검색 키워드 자연스럽게 통합
2. 시디즈 공식 데이터 근거 포함
3. 구조화된 정보
4. 브랜드 톤 유지

출처 표기 규칙 (매우 중요 - 허위 URL 절대 금지):
- 절대 패턴 기반으로 URL을 생성하지 마세요
- 실제로 존재하는 페이지 URL만 표기하세요
- 확실하지 않으면 출처를 생략하세요
- 본문 작성 후 한 줄 띄우고 "출처: [URL]" 형식으로 표기

출처 표기 가능 케이스:
- 시디즈 공식 홈페이지 메인: kr.sidiz.com
- 일반적인 브랜드 소개: 출처 생략
- 특정 제품 정보: 출처 생략 (실제 URL을 모르므로)

중요: kr.sidiz.com/product/[제품명] 같은 패턴으로 URL을 절대 생성하지 마세요.
실제 해당 페이지가 존재하는지 확인할 수 없으면 출처를 표기하지 않습니다.

변환 예시:

원본: "T50 의자"
변환:
시디즈 T50은 3단계 요추 지지 기능을 제공하는 인체공학 의자입니다.
(출처 없음 - URL을 확인할 수 없음)

원본: "시디즈 브랜드"
변환:
시디즈는 20년 이상의 인체공학 연구를 바탕으로 한 국내 대표 오피스 시팅 브랜드입니다.

출처: kr.sidiz.com
"""
    
    return f"""
{base_instruction}

{mode_instruction}

사용자 입력: "{user_input}"

위 입력을 {mode} 모드에 맞춰 변환해줘. 오직 변환된 문구만 출력하고, 부가 설명은 하지 마.
"""

# ==========================================
# 7. 세션 상태 초기화
# ==========================================
if "mode_selected" not in st.session_state:
    st.session_state.mode_selected = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_data" not in st.session_state:
    st.session_state.feedback_data = {}

if "feedback_saved" not in st.session_state:
    st.session_state.feedback_saved = set()

if "negative_feedback" not in st.session_state:
    st.session_state.negative_feedback = load_negative_feedback()

if "show_dislike_form" not in st.session_state:
    st.session_state.show_dislike_form = None

# ==========================================
# 8. 모드 선택 화면
# ==========================================
if st.session_state.mode_selected is None:
    st.title("✏️ 시디즈 UX 라이팅 가이드")
    st.markdown("### 변환 모드를 선택하세요")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎨 UX 모드")
        st.info("""
        **브랜드의 감성과 친절함에 집중**
        
        ✨ 사용자 경험 중심의 따뜻한 표현
        ✨ 전문적이면서도 접근하기 쉬운 톤
        ✨ 감성적 연결과 신뢰감 강조
        
        **추천 용도:**
        - 제품 상세 페이지 본문
        - 고객 커뮤니케이션
        - 브랜드 스토리텔링
        """)
        
        if st.button("🎨 UX 모드 선택", type="primary", use_container_width=True):
            st.session_state.mode_selected = "UX"
            st.rerun()
    
    with col2:
        st.markdown("### 🔍 SEO/GEO 모드")
        st.success("""
        **검색 최적화 + 증거 기반 문구**
        
        🔍 핵심 검색 키워드 자연스럽게 포함
        🔍 시디즈 공식 데이터 근거 제시
        🔍 검색엔진/생성형AI 친화적 구조
        🔍 브랜드 톤 유지
        
        **추천 용도:**
        - 메타 디스크립션
        - SEO 제목/설명
        - 제품명 및 카테고리 설명
        """)
        
        if st.button("🔍 SEO/GEO 모드 선택", type="primary", use_container_width=True):
            st.session_state.mode_selected = "SEO/GEO"
            st.rerun()
    
    st.markdown("---")
    st.caption("💡 모드는 언제든 변경할 수 있습니다")
    
    st.stop()

# ==========================================
# 9. 메인 UI
# ==========================================
st.title(f"✏️ 시디즈 UX 라이팅 가이드 - {st.session_state.mode_selected} 모드")

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    if st.button("🔄 모드 변경"):
        st.session_state.mode_selected = None
        st.session_state.messages = []
        st.rerun()

with col2:
    if st.button("🗑️ 대화 초기화"):
        st.session_state.messages = []
        st.session_state.feedback_data = {}
        st.session_state.feedback_saved = set()
        st.rerun()

st.markdown("---")

# ==========================================
# 10. 초기 안내 메시지
# ==========================================
if len(st.session_state.messages) == 0:
    mode_emoji = "🎨" if st.session_state.mode_selected == "UX" else "🔍"
    mode_desc = "브랜드 감성 & 친절한 조력자" if st.session_state.mode_selected == "UX" else "검색 최적화 + 증거 기반"
    
    st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**: {mode_desc}")
    
    st.markdown("### 💬 변환할 문구를 입력하세요")
    st.markdown("**예시:**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.code("편안한 의자", language=None)
        st.code("허리가 아파요", language=None)
    with col2:
        st.code("T50 의자", language=None)
        st.code("가성비 좋은 의자", language=None)

# ==========================================
# 11. 대화 내역 표시
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # 본문과 출처 분리
            content = message["content"]
            main_text = content
            source_url = None
            
            if "\n출처: " in content:
                parts = content.split("\n출처: ")
                main_text = parts[0].strip()
                source_url = parts[1].strip() if len(parts) > 1 else None
            
            # 복사 가능한 답변 표시 (항상 보이는 복사 버튼)
            copy_id = f"copy_{i}_{datetime.now().timestamp()}"
            
            # JavaScript로 답변 내용 복사
            st.markdown(f"""
            <div class="response-container" id="response-{i}">
                <div style="padding-right: 30px;">{main_text}</div>
                <button class="copy-button" onclick="copyResponse{i}()" id="copy-btn-{i}">📋</button>
            </div>
            <script>
            function copyResponse{i}() {{
                const text = `{main_text.replace('`', '\\`').replace('$', '\\$')}`;
                navigator.clipboard.writeText(text).then(() => {{
                    const btn = document.getElementById('copy-btn-{i}');
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '✓';
                    setTimeout(() => {{ btn.innerHTML = originalText; }}, 2000);
                }});
            }}
            </script>
            """, unsafe_allow_html=True)
            
            # 출처 링크 표시
            if source_url:
                if not source_url.startswith("http"):
                    source_url = "https://" + source_url
                display_url = source_url.replace("https://", "").replace("http://", "")
                st.markdown(f'<br>출처: <a href="{source_url}" target="_blank" class="source-link">{display_url}</a>', unsafe_allow_html=True)
            
            # 피드백 버튼 (마지막 메시지에만)
            if i == len(st.session_state.messages) - 1:
                st.markdown("---")
                st.markdown("**더 나은 답변을 위한 학습을 위해 피드백을 남겨주세요.**")
                
                col1, col2, col3 = st.columns([1, 1, 4])
                
                with col1:
                    if st.button("👍 좋아요", key=f"like_{i}"):
                        if i not in st.session_state.feedback_saved:
                            original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                            if save_feedback_to_sheet(original, message["content"], 1, st.session_state.mode_selected):
                                st.success("✅ 피드백 감사합니다!")
                                st.session_state.feedback_saved.add(i)
                                st.rerun()
                
                with col2:
                    if st.button("👎 싫어요", key=f"dislike_{i}"):
                        st.session_state.show_dislike_form = i
                        st.rerun()
                
                if st.session_state.show_dislike_form == i and i not in st.session_state.feedback_saved:
                    st.markdown("---")
                    st.markdown("#### 📝 피드백을 자세히 알려주세요")
                    
                    reason = st.selectbox(
                        "싫어요 사유",
                        [
                            "선택하세요",
                            "브랜드 톤이 맞지 않음",
                            "너무 형식적임",
                            "너무 길어요",
                            "너무 짧아요",
                            "키워드가 부족함",
                            "과장된 표현",
                            "원문과 너무 달라짐",
                            "출처가 부적절함",
                            "허위 URL 생성됨",
                            "기타"
                        ],
                        key=f"reason_{i}"
                    )
                    
                    comment = st.text_area(
                        "추가 코멘트 (선택사항)",
                        placeholder="구체적인 피드백을 주시면 더 나은 답변을 만드는 데 도움이 됩니다.",
                        key=f"comment_{i}",
                        height=100
                    )
                    
                    if st.button("📤 제출", key=f"submit_{i}", type="primary"):
                        if reason != "선택하세요":
                            original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                            if save_feedback_to_sheet(original, message["content"], 0, st.session_state.mode_selected, reason, comment):
                                st.success("✅ 상세한 피드백 감사합니다!")
                                st.session_state.feedback_saved.add(i)
                                st.session_state.show_dislike_form = None
                                st.session_state.negative_feedback = load_negative_feedback()
                                st.rerun()
                        else:
                            st.warning("사유를 선택해주세요.")
        else:
            # 사용자 메시지
            st.markdown(message["content"])

# ==========================================
# 12. 사용자 입력 처리
# ==========================================
prompt = st.chat_input("변환할 문구를 입력하세요...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            model = get_gemini_model()
            
            full_prompt = generate_prompt(
                st.session_state.mode_selected,
                prompt,
                st.session_state.negative_feedback
            )
            
            with st.spinner(f"시디즈 {st.session_state.mode_selected} 톤으로 변환 중..."):
                response = model.generate_content(full_prompt)
                assistant_message = response.text.strip()
            
            st.markdown(assistant_message)
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            error_str = str(e)
            
            if "429" in error_str or "quota" in error_str.lower():
                st.error("⏱️ **Gemini API 할당량 초과**")
                st.warning("잠시 후 다시 시도해주세요.")
            else:
                st.error(f"❌ 오류: {error_str}")
            
            error_message = "일시적으로 서비스를 사용할 수 없습니다."
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    st.rerun()

# ==========================================
# 13. 사이드바 통계
# ==========================================
with st.sidebar:
    st.markdown(f"### 📊 현재 모드")
    mode_emoji = "🎨" if st.session_state.mode_selected == "UX" else "🔍"
    st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**")
    
    st.markdown("---")
    
    if st.session_state.feedback_data:
        st.markdown("### 📈 피드백 통계")
        thumbs_up = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 1)
        thumbs_down = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 0)
        total = thumbs_up + thumbs_down
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👍", thumbs_up)
        with col2:
            st.metric("👎", thumbs_down)
        
        if total > 0:
            satisfaction = (thumbs_up / total) * 100
            st.progress(satisfaction / 100)
            st.caption(f"만족도: {satisfaction:.1f}%")
    
    st.markdown("---")
    st.caption("💡 부정 피드백은 자동으로 학습에 반영됩니다")
