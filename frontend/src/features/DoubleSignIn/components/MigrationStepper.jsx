import "./MigrationStepper.css";

export function MigrationStepper({ steps, currentStep }) {
  return (
    <nav className="gc-stepper-wrapper" aria-label="Sign-in migration progress">
      <ol className="gc-stepper">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isCurrent = stepNumber === currentStep;
          const isLast = index === steps.length - 1;

          return (
            <li
              key={stepNumber}
              className={`gc-stepper__item ${isCurrent ? "is-current" : ""}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <div className="gc-stepper__rail" aria-hidden="true">
                <div className="gc-stepper__dot" />
                {!isLast && <div className="gc-stepper__line" />}
              </div>

              <span className="sr-only">
                {isCurrent ? "Current step: " : "Step "}
                {stepNumber}. {step.description}
              </span>

              <div className="gc-stepper__title">Step {stepNumber}</div>
              <div className="gc-stepper__desc">{step.description}</div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
