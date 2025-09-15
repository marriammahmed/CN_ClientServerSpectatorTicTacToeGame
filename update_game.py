
import socket
import threading
from threading import Lock
import sys  # Added import for sys


class TicTacToe:
    def __init__(self):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.turn = "X"
        self.you = "X"
        self.opponent = "O"
        self.winner = None
        self.game_over = False
        self.turn_counter = 0
        self.scores = {}  # Using player names for scores
        self.player_name = ""
        self.opponent_name = ""
        self.spectator = None  # Spectator socket
        self.lock = Lock()  # To synchronize spectator updates

    def host_game(self, host, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(2)  # Support one player + one spectator
        print(f"Hosting game on {host}:{port}")

        print("Waiting for player...")
        client, address = server.accept()
        print(f"Player connected from {address}")

        # Prompt for host player's name
        self.player_name = input("Enter your name (Host): ").strip()
        print(f"Sending host name: {self.player_name}")
        client.send(self.player_name.encode("utf-8"))
        self.scores[self.player_name] = 0

        # Receive opponent name from the client
        self.opponent_name = client.recv(1024).decode("utf-8").strip()
        print(f"Opponent name: {self.opponent_name}")
        self.opponent = "O"
        self.scores[self.opponent_name] = 0

        # Start a thread for spectator (but don't block game start)
        threading.Thread(target=self.wait_for_spectator, args=(server,), daemon=True).start()

        # Start the game with a connected player
        self.handle_connection(client)

    def wait_for_spectator(self, server):
        try:
            spectator, spectator_address = server.accept()
            print(f"Spectator connected from {spectator_address}")
            self.spectator = spectator
        except Exception as e:
            print(f"Error in spectator connection: {e}")

    def connect_to_game(self, host, port):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((host, port))
        print(f"Connected to game on {host}:{port}")

        # Prompt for the connecting player's name
        self.opponent_name = input("Enter your name: ")
        client.send(self.opponent_name.encode("utf-8"))
        self.you = "O"  # Since this is the connecting player
        self.opponent = "X"
        
        # Receive host player's name
        self.player_name = client.recv(1024).decode("utf-8")
        print(f"Host name is {self.player_name}")
        self.scores[self.player_name] = 0
        self.scores[self.opponent_name] = 0

        self.handle_connection(client)

    def spectate_game(self, host, port):
        spectator = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        spectator.connect((host, port))
        print(f"Connected as a spectator to {host}:{port}")
        print("Waiting for game updates...\n")

        try:
            while True:
                data = spectator.recv(1024).decode("utf-8")
                if not data:
                    print("Game ended or connection lost.")
                    break
                print(data)
        except KeyboardInterrupt:
            print("\nDisconnected from spectating.")
        finally:
            spectator.close()

    def handle_connection(self, client):
        try:
            while True:  # Loop for replay
                self.reset_game()

                while not self.game_over:
                    if self.turn == self.you:  # Your move
                        move = input(f"{self.opponent_name}, enter your move (row,col): ")
                        if self.check_valid_move(move):
                            self.apply_move(move, self.you)
                            self.turn = self.opponent
                            client.send(move.encode("utf-8"))
                            self.notify_spectator()
                        else:
                            print("Invalid move!")
                    else:  # Opponent's move
                        data = client.recv(1024).decode("utf-8")
                        if not data:
                            print("Connection lost.")
                            return
                        if self.check_valid_move(data):
                            self.apply_move(data, self.opponent)
                            self.turn = self.you
                            self.notify_spectator()

                # Game result announcement
                if self.winner:
                    winner_name = self.player_name if self.winner == self.you else self.opponent_name
                    print(f"{winner_name} wins!")
                else:
                    print("It's a tie!")

                print(f"Scores: {self.scores}")

                # Ask for replay
                replay = input("Do you want to play again? (y/n): ").lower()
                client.send(replay.encode("utf-8"))
                opponent_replay = client.recv(1024).decode("utf-8")
                if: replay != "y" or opponent_replay != "y":
                    print("Ending session.")
                    break  # Exit replay loop

        finally:
            client.close()

    def notify_spectator(self):
        if self.spectator:
            try:
                with self.lock:  # Ensure thread safety
                    board_state = "\n".join([" | ".join(row) for row in self.board])
                    turn_message = f"Current turn: {self.player_name if self.turn == self.you else self.opponent_name}"
                    full_message = f"{turn_message}\n{board_state}\n"
                    self.spectator.send(full_message.encode("utf-8"))
            except (socket.error, BrokenPipeError):
                print("Spectator disconnected.")
                self.spectator = None

    def reset_game(self):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.turn = "X"
        self.winner = None
        self.game_over = False
        self.turn_counter = 0
        self.print_board()

    def check_valid_move(self, move):
        try:
            row, col = map(int, move.split(","))
            if 0 <= row < 3 and 0 <= col < 3:
                return self.board[row][col] == " "
            else:
                print("Move out of range! Please enter values between 0 and 2.")
            return False
        except (ValueError, IndexError):
            print("Invalid format! Please use 'row,col' format.")
            return False

    def apply_move(self, move, player):
        if self.game_over:
            return
        row, col = map(int, move.split(","))
        self.board[row][col] = player
        self.turn_counter += 1
        self.print_board()

        if self.check_if_won():
            self.winner = player
            winner_name = self.player_name if player == self.you else self.opponent_name
            print(f"{winner_name} wins!")
            self.scores[winner_name] += 1
            self.game_over = True
        elif self.turn_counter == 9:
            print("It's a tie!")
            self.game_over = True

    def check_if_won(self):
        # Rows, columns, and diagonals
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != " ":
                return True
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != " ":
                return True

        if self.board[0][0] == self.board[1][1] == self.board[2][2] != " ":
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != " ":
            return True
        return False

    def print_board(self):
        for row in self.board:
            print(" | ".join(row))
            print("-" * 8)


if __name__ == "__main__":
    game = TicTacToe()
    mode = input("Host, connect, or spectate? (h/c/s): ").lower()
    if mode == "h":
        host = input("Enter host address (default: localhost): ") or "localhost"
        port = int(input("Enter port: "))
        game.host_game(host, port)
    elif mode == "c":
        host = input("Enter host address: ")
        port = int(input("Enter port: "))
        game.connect_to_game(host, port)
    elif mode == "s":
        host = input("Enter host address: ")
        port = int(input("Enter port: "))
        game.spectate_game(host, port)
    else:
        print("Invalid mode selected.")
