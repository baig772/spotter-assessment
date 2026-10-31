import { Component, type ReactNode } from "react";

type Props = {
    children: ReactNode;
};

type State = {
    failed: boolean;
};

export default class MapErrorBoundary extends Component<Props, State> {
    state: State = { failed: false };

    static getDerivedStateFromError(): State {
        return { failed: true };
    }

    render() {
        if (this.state.failed) {
            return (
                <div role="alert" className="warning">
                    The interactive map could not load. Your route comparison remains
                    available above. Try refreshing or opening the app in a browser
                    with WebGL support.
                </div>
            );
        }

        return this.props.children;
    }
}