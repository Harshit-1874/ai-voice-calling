-- CreateTable
CREATE TABLE "contacts" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "email" TEXT,
    "company" TEXT,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "call_logs" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "callSid" TEXT NOT NULL,
    "fromNumber" TEXT NOT NULL,
    "toNumber" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "duration" INTEGER,
    "startTime" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endTime" DATETIME,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "recordingUrl" TEXT,
    "contactId" INTEGER,
    "sessionId" TEXT,
    CONSTRAINT "call_logs_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "sessions" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "call_logs_contactId_fkey" FOREIGN KEY ("contactId") REFERENCES "contacts" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sessionId" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "startTime" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "endTime" DATETIME,
    "duration" INTEGER,
    "model" TEXT NOT NULL,
    "voice" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "transcriptions" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "callLogId" INTEGER NOT NULL,
    "sessionId" TEXT,
    "timestamp" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "speaker" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "confidence" REAL,
    "isFinal" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "transcriptions_callLogId_fkey" FOREIGN KEY ("callLogId") REFERENCES "call_logs" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "conversations" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "callLogId" INTEGER NOT NULL,
    "summary" TEXT,
    "keyPoints" TEXT,
    "sentiment" TEXT,
    "leadScore" INTEGER,
    "nextAction" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "conversations_callLogId_fkey" FOREIGN KEY ("callLogId") REFERENCES "call_logs" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "contacts_phone_key" ON "contacts"("phone");

-- CreateIndex
CREATE UNIQUE INDEX "call_logs_callSid_key" ON "call_logs"("callSid");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_sessionId_key" ON "sessions"("sessionId");

-- CreateIndex
CREATE UNIQUE INDEX "conversations_callLogId_key" ON "conversations"("callLogId");
