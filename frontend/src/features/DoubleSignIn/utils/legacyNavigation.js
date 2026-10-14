const ENTRY_KEY = "canadaloginMigrationPrompt";

// A marker identifies a prompt that must be checked again when revisited.
// It is neither a cached completion result nor authentication state.
export function getPromptEntry() {
  const entry = window.history.state?.[ENTRY_KEY];
  return entry?.visited === true ? entry : null;
}

function writeEntry(entry) {
  try {
    window.history.replaceState(
      { ...window.history.state, [ENTRY_KEY]: entry },
      "",
    );
    const saved = getPromptEntry();
    return saved?.visited === true && saved?.rpClientId === entry.rpClientId;
  } catch {
    return false;
  }
}

export function preparePromptEntry() {
  return Boolean(getPromptEntry()) || writeEntry({ visited: true });
}

export function rememberPromptRpId(rpClientId) {
  if (typeof rpClientId !== "string" || !rpClientId.trim()) return false;
  return writeEntry({ visited: true, rpClientId: rpClientId.trim() });
}
