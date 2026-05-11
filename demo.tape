# VHS tape — records the opencart-cli demo GIF.
# Install vhs: brew install vhs
# Record:      vhs demo.tape    (run from the repo root)
# Output:      demo.gif
#
# Uses `opencart demo` subcommands, which render the real formatters
# against canned data — no profile or store connection needed.

Output demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 700
Set Theme "TokyoNight"
Set TypingSpeed 35ms
Set PlaybackSpeed 1.0

# Tell users we're running from a venv they'd typically have on PATH.
# For the tape we use the venv path explicitly so it works for anyone
# who clones + installs.
Hide
Type "alias oc=./.venv/bin/opencart"
Enter
Show

# Intro line
Type "# opencart-cli — operate your OpenCart store from the terminal"
Sleep 600ms
Enter
Sleep 1s

# Doctor — fast win, health check style
Type "oc demo doctor"
Sleep 300ms
Enter
Sleep 3s

# Stock — table with money formatting
Type "clear"
Enter
Type "oc demo products"
Sleep 300ms
Enter
Sleep 3s

# Sales — the money shot with sparkline + top sellers
Type "clear"
Enter
Type "oc demo sales"
Sleep 300ms
Enter
Sleep 4s

# Orders
Type "clear"
Enter
Type "oc demo orders"
Sleep 300ms
Enter
Sleep 3s

# Wrap
Type "clear"
Enter
Type "# pip install opencart-cli  →  opencart init  →  ask, watch, shell, ..."
Sleep 2s
Enter
Sleep 1s
