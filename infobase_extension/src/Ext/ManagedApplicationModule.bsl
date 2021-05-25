#Region EventHandlers

&Around("ErrorDisplayProcessing")
Procedure Sentry_ErrorDisplayProcessing(ErrorInfo, SessionTerminationRequired, StandardProcessing)
	
	ProceedWithCall(ErrorInfo, SessionTerminationRequired, StandardProcessing);
	
	StandardProcessing = False;
	ErrorProcessing.ShowErrorInfo(ErrorInfo, , , False);
	
	ErrorReport = New ErrorReport(ErrorInfo);
	If Not SessionTerminationRequired Then
		ErrorReport.AdditionalData = New Map;
		ErrorReport.AdditionalData.Insert("EventLog", Sentry_EventLogServerCall.Get());
	EndIf;
	ErrorReport.Send(False);
	
EndProcedure

#EndRegion
