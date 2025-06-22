-- CreateTable
CREATE TABLE "HubspotTempData" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "hubspotId" TEXT NOT NULL,
    "hsLeadStatus" TEXT,
    "email" TEXT,
    "phone" TEXT,
    "firstName" TEXT,
    "lastName" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "hubspotCreatedAt" TEXT
);

-- CreateIndex
CREATE UNIQUE INDEX "HubspotTempData_hubspotId_key" ON "HubspotTempData"("hubspotId");
