# Memory Index

- [Quality test coverage](project_quality_tests.md) -- 43 tests covering patchy_bot/quality.py scoring engine
- [Handler module tests](project_handler_tests.md) -- 67 tests covering extracted handler modules (search, download, chat, commands, remove)
- [Organizer test coverage](project_organizer_tests.md) -- 37 tests covering patchy_bot/plex_organizer.py parsing, file moves, and _try_remove_empty_tree path containment guard
- [Progress tracking tests](project_progress_tests.md) -- 43 tests covering download progress rendering and async tracker loop
- [Background runner tests](project_runner_tests.md) -- 31 tests covering completion poller, remove runner, schedule runner, and pure helpers
- [Callback routing tests](project_callback_tests.md) -- 22 tests covering menu/flow/stop/rm/sch callbacks and CallbackDispatcher
- [Movie schedule tests](project_movie_schedule_tests.md) -- 29 tests covering movie_tracks Store CRUD and TVMetadataClient search_movies/get_movie_release_dates
