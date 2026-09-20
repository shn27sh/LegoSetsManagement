import { Link, useNavigate } from "react-router-dom";

import { useCapabilities } from "../appMode/AppModeContext";
import { AddSetWizard } from "../components/AddSetWizard";

export function AddSetPage() {
  const navigate = useNavigate();
  const { canAddOrDuplicate } = useCapabilities();

  if (!canAddOrDuplicate) {
    return (
      <section className="page">
        <header className="page__header">
          <h1>Add set</h1>
          <p className="page__lede">
            Adding sets manually requires <strong>Edit mode</strong>. Switch mode
            in <Link to="/settings">Settings</Link>.
          </p>
        </header>
      </section>
    );
  }

  return (
    <AddSetWizard
      onClose={() => navigate(-1)}
      onCreated={(id) => navigate(`/sets/${id}`)}
    />
  );
}
