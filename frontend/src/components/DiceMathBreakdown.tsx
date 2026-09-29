import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { CombatResult } from "../api/types";

export function DiceMathBreakdown({ result }: { result: CombatResult }) {
  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {result.attacker} — {result.weapon} → {result.defender}
        </Typography>
        <Table size="small">
          <TableBody>
            {result.steps.map((step) => (
              <TableRow key={step.label}>
                <TableCell component="th" scope="row">
                  {step.label}
                </TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                  {step.value}
                </TableCell>
                <TableCell sx={{ color: "text.secondary" }}>{step.detail}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Typography sx={{ mt: 1.5, fontSize: "1.1rem" }}>
          Expected:{" "}
          <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
            {result.expected_damage}
          </Box>{" "}
          damage,{" "}
          <Box component="span" sx={{ color: "primary.main", fontWeight: 700 }}>
            {result.expected_models_slain}
          </Box>{" "}
          models slain
        </Typography>
        {result.notes.map((note) => (
          <Typography key={note} variant="body2" color="text.secondary">
            ℹ {note}
          </Typography>
        ))}
      </CardContent>
    </Card>
  );
}
