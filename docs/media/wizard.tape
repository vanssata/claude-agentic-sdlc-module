# Records the installer wizard with the `vhs` terminal recorder (https://github.com/charmbracelet/vhs).
#   vhs docs/media/wizard.tape        writes docs/media/wizard.gif
# It installs into a scratch home (--home), never into ~/.claude. Run it from the repository root.

Output docs/media/wizard.gif

Set Shell "bash"
Set FontSize 16
Set Width 1100
Set Height 700
Set Padding 20

Hide
Type "export DEMO=$(mktemp -d) && clear"
Enter
Show

Type "node bin/riskrails.js --home $DEMO/claude"
Enter
Sleep 1500ms

# runtimes: Claude Code only is what --home names; Enter confirms
Enter
Sleep 1s

# plan: move down once, back up, then Enter
Down
Sleep 700ms
Up
Sleep 700ms
Enter
Sleep 1s

# one step back, then forward again
Left
Sleep 1s
Enter
Sleep 1s

# context and statusline take their proposals (a Max plan asks about Fable first: add an Enter)
Enter
Sleep 1s
Enter
Sleep 1s

# the review screen: the dry run, "same as: <command>", then Install
Sleep 3s
Enter
Sleep 4s

Hide
Type "rm -rf $DEMO"
Enter
Show
