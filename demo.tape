# VHS tape — record a GIF demo of opencart-cli.
# Install vhs: brew install vhs
# Record:     vhs demo.tape
# Output:     demo.gif
#
# Before running, ensure you have:
#   - opencart-cli installed (`pip install -e .`)
#   - A profile configured (`opencart init`)
#   - Your terminal at a comfy size

Output demo.gif

Set Shell "zsh"
Set FontSize 14
Set Width 1000
Set Height 620
Set Theme "TokyoNight"
Set TypingSpeed 50ms
Set PlaybackSpeed 1.0

# Intro
Type "# opencart-cli — operate your OpenCart store from the terminal"
Sleep 600ms
Enter
Sleep 800ms

# Doctor
Type "opencart doctor"
Sleep 300ms
Enter
Sleep 4s

# Products
Type "clear"
Enter
Type "opencart products list --low-stock-under 5"
Sleep 300ms
Enter
Sleep 3s

# Sales — the visual one
Type "clear"
Enter
Type "opencart sales summary --days 7"
Sleep 300ms
Enter
Sleep 4s

# AI
Type "clear"
Enter
Type 'opencart ask "what is our best-selling product this week?"'
Sleep 300ms
Enter
Sleep 6s

# Wrap
Type "# pip install opencart-cli"
Enter
Sleep 1.5s
