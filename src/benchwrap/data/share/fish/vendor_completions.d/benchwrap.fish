# Autocompletion for benchwrap (fish)
if type -q benchwrap
    eval (env _BENCHWRAP_COMPLETE=fish_source benchwrap)
end
