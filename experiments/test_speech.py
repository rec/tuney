import pyttsx3
import timeit
engine = pyttsx3.init()


def save():
    print('zero')
    engine.save_to_file('Hello World' , 'test.wav')
    print('one')
    engine.runAndWait()
    print('two')


save()

# print(timeit.timeit(save, number=20))
