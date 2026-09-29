import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import { useCallback, useState, type ReactElement } from "react";

type ConfirmRequest = {
  title: string;
  message: string;
  /** Label for the destructive action. Defaults to "Delete". */
  confirmLabel?: string;
};

/**
 * Promise-based replacement for `window.confirm`, so call sites keep reading
 * `if (!(await confirm({...}))) return;` instead of threading dialog state
 * through every handler. Render the returned element anywhere in the tree.
 */
export function useConfirm(): [
  (request: ConfirmRequest) => Promise<boolean>,
  ReactElement,
] {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  const [resolve, setResolve] = useState<((ok: boolean) => void) | null>(null);

  const confirm = useCallback((next: ConfirmRequest) => {
    setRequest(next);
    return new Promise<boolean>((r) => setResolve(() => r));
  }, []);

  function close(ok: boolean) {
    resolve?.(ok);
    setResolve(null);
    setRequest(null);
  }

  const dialog = (
    <Dialog open={request !== null} onClose={() => close(false)}>
      <DialogTitle>{request?.title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{request?.message}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => close(false)}>Cancel</Button>
        <Button color="error" variant="contained" onClick={() => close(true)} autoFocus>
          {request?.confirmLabel ?? "Delete"}
        </Button>
      </DialogActions>
    </Dialog>
  );

  return [confirm, dialog];
}
