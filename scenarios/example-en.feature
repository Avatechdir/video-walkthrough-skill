Feature: Demo · adding a task (English reference scenario)
  As a skill user I want an English reference scenario,
  so that subtitles and narration come out in English end to end.

  Scenario: Add a task to the list
    Given the demo app is open in English
    When I type the text of a new task
    And I click "Add"
    Then the task appears in the list
