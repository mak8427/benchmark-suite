# Bash completion for benchwrap (Click)
_benchwrap_complete() {
    local IFS=$'\n'
    COMPREPLY=($( env _BENCHWRAP_COMPLETE=bash_complete COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD benchwrap ))
    return 0
}

complete -o default -F _benchwrap_complete benchwrap
