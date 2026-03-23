import speech_recognition as sr
from translate import Translator
import sys
import asyncio
import edge_tts
import os
import pygame

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"

async def tts(text, target_lang):
    if target_lang == "pl":
        voice = "pl-PL-MarekNeural"
    else:
        voice = "en-US-GuyNeural"

    output_file = "output.mp3"

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

        pygame.mixer.init()
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
        
        pygame.mixer.music.unload()
        pygame.mixer.quit()

        if os.path.exists(output_file):
            os.remove(output_file)
    except Exception as e:
        print(f"Błąd TTS {e}")


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


async def main():
    while True:
        print("\nWybierz język z którego chcesz przetłumaczyć:\nPowiedz 'polski' lub 'angielski'")
        print("Aby zakończyć, powiedz 'wyjdź', 'stop' lub 'koniec'")

        choose = recognise()

        if not choose:
            continue

        if "wyjdź" in choose.lower() or "stop" in choose.lower() or "koniec" in choose.lower():
            print("Zamykanie...")
            break
        elif "polski" in choose.lower():
            print("Wybrano język polski")
            src, dest, lang_code = "pl", "en", "pl-PL"
        elif "angielski" in choose.lower():
            print("Wybrano język angielski")
            src, dest, lang_code = "en", "pl", "en-US"
        else:
            print("Nie rozpoznano wyboru.")
            continue

        text = recognise(lang_code)

        if text:
            print(f"Rozpoznany tekst: {text}")
            translated_text = translate_text(text, src, dest)
            print(f"Translated: {translated_text}")
            await tts(translated_text, dest)
    

if __name__ == "__main__":
    asyncio.run(main())