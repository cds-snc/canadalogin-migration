import "./MigrationStepper.css";
import { PAGES } from "../../../utils/constants.jsx";
import { useParams } from "react-router";
import { getPageContent } from "../../../utils/functions.jsx";

export function MigrationStepper({
  steps,
  currentStep,
  showDescriptions = false,
}) {
  const { language } = useParams();

  const pageContentJson = getPageContent(language, PAGES.MigrationStepper);

  const resolvedSteps = (
    steps && steps.length
      ? steps
      : [
          { description: pageContentJson["step_1"] },
          { description: pageContentJson["step_2"] },
          { description: pageContentJson["step_3"] },
        ].filter((s) => Boolean(s?.description))
  ).filter(Boolean);

  return (
    <nav
      className="gc-stepper-wrapper"
      aria-label={pageContentJson["aria_label"]}
    >
      <ol className="gc-stepper">
        {resolvedSteps.map((step, index) => {
          const stepNumber = index + 1;
          const isCurrent = stepNumber === currentStep;
          const isLast = index === resolvedSteps.length - 1;
          const isComplete = stepNumber < currentStep;

          return (
            <li
              key={stepNumber}
              className={`gc-stepper__item ${isComplete ? "is-complete" : ""} ${isCurrent ? "is-current" : ""}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <div className="gc-stepper__rail" aria-hidden="true">
                <div className="gc-stepper__dot" />
                {!isLast && <div className="gc-stepper__line" />}
              </div>

              <span className="sr-only">
                {isCurrent
                  ? pageContentJson["sr_current_prefix"]
                  : isComplete
                    ? pageContentJson["sr_completed_prefix"]
                    : pageContentJson["sr_step_prefix"]}
                {stepNumber}. {step.description}
              </span>

              <div className="gc-stepper__title">
                <span className="gc-stepper__title-desktop">
                  {pageContentJson["step_title"].replace(
                    "{n}",
                    String(stepNumber),
                  )}
                </span>
                <span className="gc-stepper__title-mobile">{stepNumber}.</span>
              </div>
              {showDescriptions && (
                <div className="gc-stepper__desc">{step.description}</div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
