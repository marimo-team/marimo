/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default {
  title: "Dialog",
  component: Dialog,
};

export const Closed = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild={true}>
        <Button variant="outline">Rename</Button>
      </DialogTrigger>
      <DialogContent className="w-[620px] shadow-sm">
        <DialogHeader>
          <DialogTitle>Rename notebook</DialogTitle>
          <DialogDescription>
            Choose a new name for this notebook.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="name" className="text-right">
              File name
            </Label>
            <Input id="name" value="scratchpad.py" className="col-span-3" />
          </div>
        </div>
        <DialogFooter>
          <Button type="submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),

  name: "closed",
};

export const Open = {
  render: () => (
    <Dialog open={true}>
      <DialogTrigger asChild={true}>
        <Button variant="outline">Rename</Button>
      </DialogTrigger>
      <DialogContent className="w-[620px] shadow-sm">
        <DialogHeader>
          <DialogTitle>Rename notebook</DialogTitle>
          <DialogDescription>
            Choose a new name for this notebook.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="name" className="text-right">
              File name
            </Label>
            <Input id="name" value="scratchpad.py" className="col-span-3" />
          </div>
        </div>
        <DialogFooter>
          <Button type="submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),

  name: "open",
};
