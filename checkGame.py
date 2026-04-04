class chckGame:
    def checkGame(puzzle, player, progression, db):
        solution_row = db.get_solution(puzzle.seed)
        if not solution_row:
            print("No solution found for seed:", puzzle.seed)
            return False
        solution = solution_row["solution_data"]
        if puzzle.grid == solution:
            print("it's correct")

            puzzle.stop_timer()
            elapsed_time = puzzle.get_elapsed_time()