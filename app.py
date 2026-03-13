import speech_recognition as sr
import pyttsx3
from translate import Translator

engine = pyttsx3.init()
engine.setProperty('rate', 150)

def recognise():
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Powiedz cos...")
        audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio, language='pl-PL')
            return text
        except sr.UnknownValueError:
            return "Nie zrozumiano"
        except sr.RequestError:
            return "Błąd połączenia z serwerem"
        
        
def translate_text(text, from_="pl", to_="en"):
    translator = Translator(from_lang=from_, to_lang=to_)

    try:
        result = translator.translate(text)
        return result
    except Exception as e:
        return f"Translate error: {str(e)}"


text = recognise()
translated_text = translate_text(text, "pl", "en")
print(translated_text)