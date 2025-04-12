import streamlit as st
import nltk
from nltk.tokenize import word_tokenize
from deep_translator import GoogleTranslator
import pyperclip
import pdfplumber
import sqlite3
from docx import Document
from googletrans import LANGUAGES  # To get all languages

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('app.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')  # User table for registration
    c.execute('''CREATE TABLE IF NOT EXISTS texts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, username TEXT)''')  # Texts table to save user texts
    conn.commit()
    return conn

conn = init_db()

# Download NLTK data
def download_nltk_resources():
    resources = ['punkt', 'stopwords', 'wordnet']
    for resource in resources:
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            nltk.download(resource)

download_nltk_resources()

# Lemmatize Text
def lemmatize_text(text):
    lemmatizer = nltk.WordNetLemmatizer()
    words = word_tokenize(text)
    lemmatized_words = [lemmatizer.lemmatize(word) for word in words]
    return " ".join(lemmatized_words)

# Remove common words (and numbers) from text
def remove_common_words(text):
    custom_stopwords = set(nltk.corpus.stopwords.words("english")).union({
        "initially", "essentially", "basically", "usually", "often", "sometimes"
    })
    words = word_tokenize(text)
    filtered_words = [word for word in words if word.lower() not in custom_stopwords and not word.isdigit()]
    return " ".join(filtered_words)

# Summarize Text
def summarize_text(text, word_count=100):
    if not text:
        return "Text is empty. Please provide text to summarize."
    
    sentences = nltk.sent_tokenize(text)
    if len(sentences) == 0:
        return "The text is too short for summarization."
    
    text = lemmatize_text(text)
    text = remove_common_words(text)
    
    stop_words = set(nltk.corpus.stopwords.words("english"))
    words = word_tokenize(text.lower())
    freq_table = {word: words.count(word) for word in words if word.isalnum() and word not in stop_words}
    
    sentence_scores = {sentence: sum(freq_table.get(word, 0) for word in nltk.word_tokenize(sentence.lower())) for sentence in sentences}
    
    if not sentence_scores:
        return "Could not generate summary, please check the text."
    
    sorted_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)
    
    summary, total_words = [], 0
    seen_sentences = set()  # To track already included sentences
    
    for sentence in sorted_sentences:
        if sentence not in seen_sentences:
            words_in_sentence = len(nltk.word_tokenize(sentence))
            if total_words + words_in_sentence <= word_count:
                summary.append(sentence)
                total_words += words_in_sentence
                seen_sentences.add(sentence)
            else:
                break
    
    if not summary:
        return "Summary could not be generated due to insufficient content."
    
    return " ".join(summary)

# Extract High-Weight Keywords from Text
def extract_keywords(text):
    # Tokenize the text and remove stopwords
    stop_words = set(nltk.corpus.stopwords.words("english"))
    words = word_tokenize(text.lower())
    
    # Filter out stopwords and non-alphanumeric words (e.g., punctuation)
    filtered_words = [word for word in words if word.isalnum() and word not in stop_words]
    
    # Create frequency distribution of the words
    freq_dist = nltk.FreqDist(filtered_words)
    
    # Extract the top keywords based on frequency (you can adjust this to get more or fewer keywords)
    keywords = [word for word, _ in freq_dist.most_common(20)]  # Top 20 frequent words
    
    return keywords

# Translate Text
def translate_text(text, dest_language='te'):
    if not text:
        st.warning("Please provide text to translate.")
        return ""
    
    # Check if the language is supported
    if dest_language not in LANGUAGES:
        st.warning(f"Translation error: '{dest_language}' is not supported. Please select one of the supported languages.")
        return ""
    
    max_length = 50000  # Increase max length for translation
    if len(text) > max_length:
        st.warning(f"Text is too long (greater than {max_length} characters). Splitting text for translation.")
        
        chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
        translated_chunks = []
        
        for chunk in chunks:
            try:
                translated_text = GoogleTranslator(source='auto', target=dest_language).translate(chunk)
                translated_chunks.append(translated_text)
            except Exception as e:
                st.error(f"Translation failed for chunk: {e}")
                return "Translation failed. Please try again later."

        return " ".join(translated_chunks)
    
    try:
        translated_text = GoogleTranslator(source='auto', target=dest_language).translate(text)
        return translated_text
    except Exception as e:
        st.error(f"Translation error: {e}")
        return "Translation failed. Please try again later."

# Registration Page
def register_page():
    st.title("Register")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Register"):
        if username and password:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            if c.fetchone():
                st.warning("Username already exists!")
            else:
                c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                st.success("Registration successful! Please log in.")
        else:
            st.warning("Please provide both username and password.")

# Login Page
def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username and password:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            if c.fetchone():
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.selected_text = ""  # Reset selected text after login
                st.rerun()
            else:
                st.error("Invalid username or password.")
        else:
            st.warning("Please enter both username and password.")

# Dashboard Page
def dashboard_page():
    st.title(f"Welcome, {st.session_state.username}")
    st.sidebar.title("Options")
    option = st.sidebar.radio("Choose an option", ["Summarize Text", "Translate Text", "Upload File"])

    # Main Functionality
    if option == "Summarize Text":
        text = st.text_area("Enter your text here", height=200)
        if text:
            summary_type = st.radio("Summary Type", ["Keywords", "Summarize in Given Words"])
            if summary_type == "Keywords":
                # Extract and display the keywords from the text
                keywords = extract_keywords(text)
                st.markdown("**Keywords**")  # Bold and capitalized heading
                st.write(", ".join(keywords))  # Just display the keywords without selection
            elif summary_type == "Summarize in Given Words":
                word_count = st.number_input("Enter the number of words", min_value=10, max_value=2000, value=100)
                st.write("Summary:", summarize_text(text, word_count))

    elif option == "Translate Text":
        text = st.text_area("Enter text to translate", value=st.session_state.selected_text)
        if text:
            language = st.selectbox("Select Language", list(LANGUAGES.values()))  # Dropdown of languages
            lang_code = [code for code, name in LANGUAGES.items() if name == language][0]
            translation = translate_text(text, dest_language=lang_code)
            st.write("Translated Text:", translation)

    elif option == "Upload File":
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])
        if uploaded_file is not None:
            if uploaded_file.type == "application/pdf":
                with pdfplumber.open(uploaded_file) as pdf:
                    text = " ".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc = Document(uploaded_file)
                text = " ".join([para.text for para in doc.paragraphs])

            if text:
                st.text_area("Extracted Text", text, height=200)
                
                # Keyword extraction
                keywords = extract_keywords(text)
                st.markdown("**Keywords**")  # Bold and capitalized heading
                st.write(", ".join(keywords))  # Just display the keywords without selection
                
                word_count = st.number_input("Enter the number of words for the summary", min_value=10, max_value=2000, value=100)
                st.write("Summary:", summarize_text(text, word_count))

    # Copy Functionality
    if 'text' in locals() and text:
        if st.button("Copy Text"):
            pyperclip.copy(text)
            st.success("Copied to clipboard!")

    # Logout
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.selected_text = ""  # Clear selected text on logout
        st.rerun()

# Function to inject custom CSS styling
def get_styling():
    return """
    <style>
      
        body {
            background-color: #e8f5e9;
            font-family: Arial, sans-serif;
        }

        /* General Background */
        body {
            background-color: #f0f0f5;
            font-family: Arial, sans-serif;
        }

        /* Sidebar Styling */
        .sidebar .sidebar-content {
            background-color: #1e1e1e;
            color: white;
        }
        .sidebar .sidebar-content .sidebar-header {
            background-color: #3b8e3b;
        }

        /* Login and Register pages */
        .stTextInput>div>div>input {
            background-color: #e7e7e7;
            border-radius: 5px;
            border: 1px solid #ddd;
            padding: 10px;
        }
        .stTextInput>div>div>input:focus {
            border-color: #4CAF50;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
        }
        .stButton>button:hover {
            background-color: #45a049;
        }

        /* Dashboard Page */
        .stTextArea>div>div>textarea {
            background-color: #e7e7e7;
            border-radius: 5px;
            border: 1px solid #ddd;
            padding: 10px;
        }
        .stTextArea>div>div>textarea:focus {
            border-color: #4CAF50;
        }

        /* Section Headings */
        h1 {
            color: #3b8e3b;
            font-size: 2em;
        }
        h2 {
            color: #1e1e1e;
            font-size: 1.5em;
        }

        /* Buttons */
        .stButton>button {
            background-color: #0077cc;
            color: white;
            border-radius: 5px;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
        }

        .stButton>button:hover {
            background-color: #005fa3;
        }

        /* Text Styling */
        .stWarning {
            color: #FF9800;
            font-weight: bold;
        }
        .stSuccess {
            color: #4CAF50;
            font-weight: bold;
        }
        .stError {
            color: #f44336;
            font-weight: bold;
        }

        /* File Upload Area */
        .stFileUploader {
            background-color: #f0f0f5;
            border-radius: 5px;
            padding: 20px;
            border: 2px dashed #0077cc;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        ::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 10px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }

    </style>
    """


# Main App Logic
def main():
    # Inject custom styles
    st.markdown(get_styling(), unsafe_allow_html=True)

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        option = st.radio("Choose an option", ["Login", "Register"])
        if option == "Login":
            login_page()
        elif option == "Register":
            register_page()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()
