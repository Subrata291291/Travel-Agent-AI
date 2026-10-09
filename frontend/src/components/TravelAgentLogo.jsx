import robotLogo from "../assets/travel-agent-robot.png";

function TravelAgentLogo({ className = "h-11 w-11" }) {
  return (
    <span className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-xl bg-slate-900 ${className}`}>
      <img
        src={robotLogo}
        alt=""
        aria-hidden="true"
        className="h-full w-full object-contain p-0.5"
      />
    </span>
  );
}

export default TravelAgentLogo;
