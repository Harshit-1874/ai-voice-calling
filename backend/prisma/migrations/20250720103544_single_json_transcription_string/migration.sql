/*
  Warnings:

  - You are about to drop the `transcriptions` table. If the table is not empty, all the data it contains will be lost.

*/
-- DropTable
PRAGMA foreign_keys=off;
DROP TABLE "transcriptions";
PRAGMA foreign_keys=on;

-- CreateTable
CREATE TABLE "Transcription" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "callLogId" INTEGER NOT NULL,
    "transcript" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Transcription_callLogId_fkey" FOREIGN KEY ("callLogId") REFERENCES "call_logs" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Transcription_callLogId_key" ON "Transcription"("callLogId");
