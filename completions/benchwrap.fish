# Autocompletion for benchwrap (Click-based)
# Installed as a vendor completion so it works immediately after install.
# This evaluates Click's dynamic completion script on shell startup.

# Guard to avoid errors if the command isn't on PATH yet
if type -q benchwrap
    eval (env _BENCHWRAP_COMPLETE=fish_source benchwrap)
end
