import { memo } from "react";
import { python } from "@codemirror/lang-python";
import CodeMirror, {
  EditorView,
  ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import { CopyIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Events } from "@/utils/events";
import { toast } from "@/components/ui/use-toast";
import { useThemeForPlugin } from "@/theme/useTheme";
import { cn } from "@/utils/cn";

export const ReadonlyPythonCode = memo(
  (props: { className?: string; code: string } & ReactCodeMirrorProps) => {
    const { theme } = useThemeForPlugin();
    const { code, className, ...rest } = props;
    return (
      <div className={cn("relative hover-actions-parent", props.className)}>
        <FloatingCopyButton text={props.code} />
        <CodeMirror
          {...rest}
          className="cm"
          theme={theme === "dark" ? "dark" : "light"}
          height="100%"
          editable={true}
          extensions={[python(), EditorView.lineWrapping]}
          value={props.code}
          readOnly={true}
        />
      </div>
    );
  }
);

const FloatingCopyButton = (props: { text: string }) => {
  const copy = Events.stopPropagation(() => {
    navigator.clipboard.writeText(props.text);
    toast({ title: "Copied to clipboard" });
  });

  return (
    <Button
      onClick={copy}
      className="absolute top-0 right-0 m-1 z-10 hover-action"
      size="xs"
      variant="secondary"
    >
      <CopyIcon size={14} strokeWidth={1.5} />
    </Button>
  );
};
