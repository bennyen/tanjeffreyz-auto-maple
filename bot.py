"""An interpreter that reads and executes user-created routines."""

import config
import threading
import winsound
import time
import csv
import mss
import utils
import pygame
import inspect
import keyboard as kb
from os import listdir
from os.path import isfile, join, splitext
from vkeys import press
from layout import Layout


class Point:
    """Represents a location in a user-defined routine."""

    def __init__(self, x, y, frequency=1, counter=0):
        self.location = (float(x), float(y))
        self.frequency = utils.validate_nonzero_int(frequency)
        self.counter = int(counter)
        self.commands = []

    @utils.run_if_enabled
    def execute(self):
        """
        Executes the set of actions associated with this Point.
        :return:    None
        """

        if self.counter == 0:
            move = config.command_book.get('move')      # TODO: catch move does not exist, don't move, just disable bot
            if config.enabled:
                print()
                print(self._heading())
            move(*self.location).execute()
            for command in self.commands:
                command.execute()
        self._increment_counter()

    @utils.run_if_enabled
    def _increment_counter(self):
        """
        Increments this Point's counter, wrapping back to 0 at the upper bound.
        :return:    None
        """

        self.counter = (self.counter + 1) % self.frequency

    def __str__(self):
        """
        Returns a string representation of this Point object.
        :return:    This Point's string representation.
        """

        result = self._heading()
        for command in self.commands:
            result = result + '\n' + str(command)
        return result

    def _heading(self):
        """
        Returns this Point's heading for display purposes.
        :return:    This Point's heading.
        """

        return f'Point at {self.location}' + (':' if self.commands else '')


class Bot:
    """A class that interprets and executes user-defined routines."""

    alert = None

    def __init__(self):
        """Loads a user-defined routine on start up and initializes this Bot's main thread."""

        pygame.mixer.init()
        Bot.alert = pygame.mixer.music
        Bot.alert.load('./assets/alert.mp3')
        Bot.load_commands()
        Bot.load_routine()
        self.thread = threading.Thread(target=Bot._main)
        self.thread.daemon = True

    def start(self):
        """
        Starts this Bot object's thread.
        :return:    None
        """

        print('\nStarted main bot loop.')
        self.thread.start()

    @staticmethod
    def _main():
        """
        The main body of Bot that executes the user's routine.
        :return:    None
        """

        with mss.mss() as sct:
            buff = Bot._buff(['f1', 'f2', 'f4'])
            while True:
                if config.elite_active:
                    Bot._elite_alert()
                if config.enabled:
                    buff = buff()
                    element = config.sequence[config.seq_index]
                    if isinstance(element, Point):
                        element.execute()
                        if config.rune_active and element.location == config.rune_index:
                            Bot._solve_rune()
                    Bot._step()
                else:
                    time.sleep(0.01)

    @staticmethod
    @utils.run_if_enabled
    def _solve_rune():
        """
        Moves to the position of the rune and solves the arrow-key puzzle.
        :return:    None
        """

        move = config.command_book.get('move')
        move(*config.rune_pos).execute()
        print("\n\n\n\n\n\nWENT TO THE RUNE!!!\n\n\n\n\n\n")            # TODO: finish solving rune here

    @staticmethod
    def _elite_alert():
        """
        Plays an alert to notify user of an Elite Boss spawn. Stops the alert
        once 'insert' is pressed.
        :return:    None
        """

        config.listening = False
        Bot.alert.play(-1)
        while not kb.is_pressed('insert'):
            time.sleep(0.1)
        Bot.alert.stop()
        config.elite_active = False
        time.sleep(1)
        config.listening = True

    @staticmethod
    @utils.run_if_enabled
    def _step():
        """
        Increments config.seq_index and wraps back to 0 at the end of config.sequence.
        :return:    None
        """

        config.seq_index = (config.seq_index + 1) % len(config.sequence)

    @staticmethod
    def _buff(skills, haku_time=0.0, buff_time=0.0):
        def act():
            nonlocal haku_time, buff_time
            now = time.time()
            if haku_time == 0 or now - haku_time > 490:
                press('ctrl', 2)
                haku_time = now
            if buff_time == 0 or now - buff_time > config.buff_cooldown:
                for s in skills:
                    press(s, 3, up_time=0.3)
                    buff_time = now
            return Bot._buff(skills, haku_time, buff_time)
        return act

    @staticmethod
    def load_commands():
        """
        Prompts the user to select a command module to import. Updates config's command book.
        :return:    None
        """

        utils.print_separator()
        print('~~~ Loading Command Book ~~~')
        module_name = Bot._select_file('./commands', '.py')
        module_name = splitext(module_name)[0]
        module = __import__(f'commands.{module_name}', fromlist=[''])
        config.command_book = {}
        for name, command in inspect.getmembers(module, inspect.isclass):
            name = name.lower()
            config.command_book[name] = command

    @staticmethod
    def load_routine(file=None):
        """
        Attempts to load FILE into a sequence of Points. Prompts user input if no file is given.
        :param file:    The file's path.
        :return:        None
        """

        routines_dir = './routines'
        if not file:
            utils.print_separator()
            print('~~~ Loading Routine ~~~')
            file = Bot._select_file(routines_dir, '.csv')
        if file:
            config.calibrated = False
            utils.print_separator()
            print(f"Loading routine '{file}'...")
            config.sequence = []
            config.seq_index = 0
            with open(join(routines_dir, file), newline='') as f:
                csv_reader = csv.reader(f, skipinitialspace=True)
                curr_point = None
                line = 1
                for row in csv_reader:
                    result = Bot._eval(row, line)
                    if result:
                        if isinstance(result, utils.Command):
                            if curr_point:
                                curr_point.commands.append(result)
                        else:
                            config.sequence.append(result)
                            if isinstance(result, Point):
                                curr_point = result
                    line += 1
            config.routine = file
            config.layout = Layout.load(file)
            print(f"Finished loading routine '{file}'.")
            winsound.Beep(523, 200)     # C5
            winsound.Beep(659, 200)     # E5
            winsound.Beep(784, 200)     # G5

    @staticmethod
    def _eval(expr, n):
        """
        Evaluates the given expression EXPR in the context of Auto Kanna.
        :param expr:    A list of strings to evaluate.
        :param n:       The line number of EXPR in the routine file.
        :return:        An object that represents EXPR.
        """

        if expr and isinstance(expr, list):
            first, rest = expr[0], expr[1:]
            rest = [s.strip() for s in rest]
            line = f'Line {n}: '
            if first == '@':        # Check for labels
                if len(rest) != 1:
                    print(line + f'Incorrect number of arguments for a label.')
                else:
                    return rest[0]
            elif first == '*':      # Check for Points
                try:
                    return Point(*rest)
                except ValueError:
                    print(line + f'Invalid arguments for a Point: {rest}')
                except TypeError:
                    print(line + f'Incorrect number of arguments for a Point.')
            else:                   # Otherwise might be a Command
                if first not in config.command_book.keys():
                    print(line + f"Command '{first}' does not exist.")
                else:
                    try:
                        return config.command_book.get(first)(*rest)
                    except ValueError:
                        print(line + f"Invalid arguments for command '{first}': {rest}")
                    except TypeError:
                        print(line + f"Incorrect number of arguments for command '{first}'.")

    @staticmethod
    def _select_file(directory, extension):
        """
        Prompts the user to select a file from the .csv files within DIRECTORY.
        :param directory:   The directory in which to search.
        :param extension:   The file extension for which to filter by.
        :return:            The path of the selected file.
        """

        index = float('inf')
        valid_files = [f for f in listdir(directory) if isfile(join(directory, f)) and extension in f]
        num_files = len(valid_files)
        if not valid_files:
            print(f"Unable to find any '{extension}' files in '{directory}'.")
        else:
            print('Please select from the following files:\n')
            for i in range(num_files):
                print(f'{i:02} -- {valid_files[i]}')
            print()

            selection = 0
            while index not in range(num_files):
                try:
                    selection = input('>>> ')
                except KeyboardInterrupt:
                    exit()

                if not utils.validate_type(selection, int):
                    print('Selection must be an integer.')
                else:
                    index = int(selection)
                    if index not in range(num_files):
                        print(f'Please enter an integer between 0 and {max(0, num_files - 1)}.')
            return valid_files[index]

    @staticmethod
    def toggle_enabled():
        """
        Resumes or pauses the current routine. Plays a sound and prints a message to notify
        the user.
        :return:    None
        """

        config.rune_active = False
        config.elite_active = False
        utils.print_separator()
        print(f"Toggled: {'OFF' if config.enabled else 'ON'}")
        config.enabled = not config.enabled
        if config.enabled:
            winsound.Beep(784, 333)     # G5
        else:
            winsound.Beep(523, 333)     # C5
