import { useMemo } from 'react'
import './PacingBar.css'

/**
 * PacingBar Component - The "Pacing" Layer
 *
 * Visual progress bar showing narrative pacing for ONE_SHOT sessions.
 *
 * Props:
 *   currentTurn: number - Current turn (1-indexed)
 *   maxTurns: number - Maximum turns (default 20)
 *   sessionScope: "ONE_SHOT" | "CAMPAIGN"
 */
export function PacingBar({
  currentTurn = 0,
  maxTurns = 20,
  sessionScope = "ONE_SHOT"
}) {
  // Don't show for CAMPAIGN mode
  if (sessionScope === "CAMPAIGN") {
    return null
  }

  const { phase, phaseLabel, progress, phaseProgress } = useMemo(() => {
    const turn = Math.max(0, currentTurn)
    const progress = Math.min((turn / maxTurns) * 100, 100)

    let phase, phaseLabel, phaseProgress

    if (turn <= 5) {
      phase = "intro"
      phaseLabel = "Act I: The Hook"
      phaseProgress = (turn / 5) * 100
    } else if (turn <= 15) {
      phase = "rising"
      phaseLabel = "Act II: The Struggle"
      phaseProgress = ((turn - 5) / 10) * 100
    } else {
      phase = "climax"
      phaseLabel = "Act III: The Climax"
      phaseProgress = ((turn - 15) / 5) * 100
    }

    return { phase, phaseLabel, progress, phaseProgress }
  }, [currentTurn, maxTurns])

  const turnsRemaining = Math.max(0, maxTurns - currentTurn)

  return (
    <div className="pacing-bar">
      <div className="pacing-bar__track">
        <div
          className={`pacing-bar__fill pacing-bar__fill--${phase}`}
          style={{ width: `${progress}%` }}
        />
        {/* Act markers */}
        <div className="pacing-bar__marker" style={{ left: '25%' }} />
        <div className="pacing-bar__marker" style={{ left: '75%' }} />
      </div>
      <div className="pacing-bar__info">
        <span className={`pacing-bar__phase pacing-bar__phase--${phase}`}>
          {phaseLabel}
        </span>
        <span className="pacing-bar__turns">
          {turnsRemaining > 0 ? (
            <>Turn {currentTurn} of {maxTurns}</>
          ) : (
            <span className="pacing-bar__finale">Final Act</span>
          )}
        </span>
      </div>
    </div>
  )
}

export default PacingBar
