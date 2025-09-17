import React from "react";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Button from "@mui/material/Button";

function ArchitectureDiagramDialog({ open, onClose, src }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      PaperProps={{
        style: {
          maxWidth: "90vw",
          maxHeight: "90vh",
          margin: "auto"
        }
      }}
    >
      <DialogTitle>Data Analyst Assistant Architecture Diagram</DialogTitle>
      <DialogContent style={{ padding: "16px", display: "flex", justifyContent: "center" }}>
        {src ? (
          <img
            src={src}
            style={{
              maxWidth: "100%",
              maxHeight: "calc(90vh - 120px)",
              objectFit: "contain",
              height: "auto",
              width: "auto"
            }}
            alt="Powered By AWS"
          />
        ) : (
          <div style={{ textAlign: "center", padding: "20px" }}>
            No diagram available
          </div>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default ArchitectureDiagramDialog;