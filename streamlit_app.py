import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 보안 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except KeyError:
    st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다. 관리자 설정을 확인해주세요.")
    st.stop()

# ==========================================
# 2. 브랜드 가이드라인
# ==========================================
SYSTEM_INSTRUCTION = """
너는 시디즈의 UX 라이터야. 일반적인 문구를 시디즈만의 [전문적/세심한/혁신적] 톤으로 바꿔줘.
아래는 시디즈 홈페이지에서 가져온 브랜드 문구들이야. 이 말투와 단어 선택을 학습해서 내 문장을 변환해줘.

[참고 문구]
- 시디즈의 디자인은 사용자로부터 시작됩니다. 누가 앉을지, 어떤 상황에서 쓰일지 고민하여 최상의 의자 위 경험이라는 시팅 솔루션을 구현해냅니다.
- 인체에 대한 다양한 연구와 공학적 설계를 통해 누구든지 편안하게 사용할 수 있는 제품을 완성합니다.
- 언제나 새로운 시도를 주저 않고, 전문성을 더해 의자 위의 가장 진보된 경험을 만듭니다.
- 제품 구매가 기능적 가치를 넘어 지속가능성을 이루는 방식이 되도록 책임을 다합니다.
- 어떤 상황과 자세에서도 유연하게 반응하며 모든 니즈에 대응하는 퍼포먼스 공학 의자와 함께하세요.
"""

# ==========================================
# 3. 모델 초기화 (올바른 모델 이름 사용)
# ==========================================
@st.cache_resource
def get_gemini_model():
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",  # 또는 "models/gemini-1.5-flash"
        system_instruction=SYSTEM_INSTRUCTION
    )

# ==========================================
# 4. UI 구성
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺")
st.title("💺 시디즈 UX 라이팅 번역기")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_data" not in st.session_state:
    st.session_state.feedback_data = {}

# ==========================================
# 5. 대화 내역 표시
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # 최신 assistant 메시지에만 피드백 버튼 표시
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            feedback = st.feedback("thumbs", key=f"feedback_{i}")
            
            if feedback is not None:
                st.session_state.feedback_data[i] = {
                    "message": message["content"],
                    "feedback": feedback,
                    "prompt": st.session_state.messages[i-1]["content"] if i > 0 else ""
                }

# ==========================================
# 6. 사용자 입력 처리
# ==========================================
if prompt := st.chat_input("수정할 문구를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            model = get_gemini_model()
            response = model.generate_content(prompt)
            assistant_message = response.text
            
            st.markdown(assistant_message)
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            error_message = f"오류가 발생했습니다: {str(e)}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# ==========================================
# 7. 사이드바
# ==========================================
with st.sidebar:
    st.header("🎯 사용 가이드")
    st.markdown("""
    1. 일반 문구를 입력하세요
    2. 시디즈 톤으로 변환된 결과를 확인하세요
    3. 만족도를 👍/👎로 평가해주세요
    """)
    
    if st.button("대화 내역 초기화"):
        st.session_state.messages = []
        st.session_state.feedback_data = {}
        st.rerun()
    
    if st.session_state.feedback_data:
        st.divider()
        st.subheader("📊 피드백 통계")
        thumbs_up = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 1)
        thumbs_down = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 0)
        st.metric("긍정", thumbs_up)
        st.metric("부정", thumbs_down)
