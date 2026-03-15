import speech_recognition as sr
from translate import Translator
import sys
import asyncio
import edge_tts
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame

async def tts(text, lang):
    if "pl-PL" in lang:
        voice = "en-US-GuyNeural"
    else:
        voice = "pl-PL-MarekNeural"

    output_file = "output.mp3"

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

    pygame.mixer.init()
    pygame.mixer.music.load(output_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.1)
    
    pygame.mixer.quit()

    if os.path.exists(output_file):
        os.remove(output_file)


def recognise(lang="pl-PL"):
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Powiedz coś...")
        audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio, language=lang)
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
        return f"Błąd tłumaczenia: {str(e)}"


def choose_language():
    while True:
        print("\nWybierz język z którego chcesz przetłumaczyć:\nPowiedz 'polski' lub 'angielski'")
        print("Aby zakończyć, powiedz 'wyjdź', 'stop' lub 'koniec'")

        choose = recognise()

        if not choose:
            print("Nie wykryto mowy, spróbuj jeszcze raz...")
            continue

        if "wyjdź" in choose.lower() or "stop" in choose.lower() or "koniec" in choose.lower():
            sys.exit()
        elif "polski" in choose.lower():
            print("Wybrano język polski")
            return "pl-PL"
        elif "angielski" in choose.lower():
            print("Wybrano język angielski")
            return "en-US"
        else:
            print("Nie rozpoznano języka, spróbuj ponownie...")


async def main():
    while True:
        lang = choose_language()

        text = recognise(lang)

        if lang == "pl-PL":
            print(f"Rozpoznany tekst: {text}")
            translated_text = translate_text(text, "pl", "en")
            print(f"Translated: {translated_text}")
            await tts(translated_text, lang)
        else:
            print(f"Recognized text: {text}")
            translated_text = translate_text(text, "en", "pl")
            print(f"Translated: {translated_text}")
            await tts(translated_text, lang)

if __name__ == "__main__":
    asyncio.run(main())