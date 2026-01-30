import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 보안 설정 (Secrets에서 키 가져오기)
# ==========================================
try:
    # Streamlit Cloud의 Secrets 설정에서 키를 읽어옵니다.
    GOOGLE_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except KeyError:
    st.error("Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다. 관리자 설정을 확인해주세요.")
    st.stop()

# ==========================================
# 2. 브랜드 가이드라인 (핵심 내용만 추출)
# ==========================================
# AI Studio에서 작성하신 프롬프트의 핵심만 남겼습니다.
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
# 3. UI 구성 및 채팅 로직
# ==========================================
st.set_page_config(page_title="시디즈 UX 번역기", page_icon="💺")
st.title("💺 시디즈 UX 라이팅 번역기")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 내역 표시 및 피드백 버튼
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            # 엄지척 피드백 수집
            st.feedback("thumbs", key=f"feedback_{i}")

# 사용자 입력 처리
if prompt := st.chat_input("수정할 문구를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Gemini 모델 호출 (System Instruction 포함)
        model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest", # 또는 "models/gemini-1.5-flash"
    system_instruction=SYSTEM_INSTRUCTION
    )
        response = model.generate_content(prompt)
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
