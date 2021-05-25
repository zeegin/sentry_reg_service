// BSLLS-off:NestedFunctionInParameters

#Region Public

Function Get() Export
	
	// Последние $Max событий журнала регистрации текущего сеанса.
	
	Filter = New Structure;
	Filter.Insert("Session", InfoBaseSessionNumber());
	Max = 15;
	
	EventLog = New ValueTable;
	UnloadEventLog(EventLog, Filter, , , Max);
	
	Result = New Array;
	For Line = 0 To Max - 1 Do
		
		// Платформа может вернуть больше, чем мы просили в $Max
		// Берем последние $Max событий из журнала регистрации.
		Event = EventLog[EventLog.Count() - Max + Line];
		
		If Metadata.ScriptVariant = Metadata.ObjectProperties.ScriptVariant.English Then
			Level     = Event.Level;
			EventName = Event.Event;
			Date      = Event.Date;
			Comment   = Event.Comment;
			Meta      = Event.Metadata;
			Data      = Event.Data;
		Else
			Level     = Event.Уровень;
			EventName = Event.Событие;
			Date      = Event.Дата;
			Comment   = Event.Комментарий;
			Meta      = Event.Метаданные;
			Data      = Event.Данные;
		EndIf;
		
		Record = New Structure;
		Record.Insert("Level", String(Level));
		Record.Insert("EventName", EventName);
		Record.Insert("Date", WriteJSONDate(
			Date,
			JSONDateFormat.ISO,
			JSONDateWritingVariant.UniversalDate
		));
		Record.Insert("Comment", Comment);
		Record.Insert("Meta", String(Meta));
		Record.Insert("Data", String(Data));
		
		Result.Add(Record);
	EndDo;
	Return Result;
	
EndFunction

#EndRegion
