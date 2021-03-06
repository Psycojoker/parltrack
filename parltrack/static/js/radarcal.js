$(document).ready(function() {
    var eventclasses={
      'Council: debate or examination expected' : 'council-debate-expected',
      'Council: final act scheduled' : 'council-final',
      'Council: political agreement on final act expected' : 'council-agree',
      'EP plenary sitting (indicative date)' : 'ep-sitting',
      'EP plenary sitting, 2nd reading (indicative date)' : 'ep-2ndsitting',
      'EP plenary sitting, 3rd reading (indicative date)' : 'ep-3rdsitting',
      'Plenary sitting agenda, debate' : 'ep-debate',
      'EP: report scheduled for adoption in committee, 1st or single reading' : 'ep-1streading',
      'EP: report scheduled for adoption in committee, 1st or single reading' : 'ep-1streading',
      'EP: report scheduled for adoption in committee, 2nd reading': 'ep-2ndreading',
      'Plenary sitting agenda, vote' :  'ep-vote'
    };
    var events=[];
    $('.vevent').each(function() {
       var eventclass=$(this).find('span.summary').text();
       events.push( {
          title : $(this).parent().prev().text(),
          summary : $(this).parent().next().next().next().text(),
          type  : eventclass,
          url   : $(this).parent().prev().find("a").attr('href'),
          start : $(this).find(".dtstart").text(),
          className: eventclasses[eventclass]
       });
    });
    $('#categories').hide();
    $('#legend').show();
    $('#calendar').fullCalendar({
        events : events,
        weekends: false,
        weekMode: 'liquid',
        contentHeight: 500,
        defaultView: "month",
        eventRender: function(event, element) {
          element.qtip({content: '<div class="'+eventclasses[event.type]+'">'+event.type+"</div><div>"+event.summary+"</div>",
                        tip: 'bottomLeft',
                        style: {
                          padding: 2,
                          border: { width: 2 }},
                        position: {
                          corner: {
                            target: 'mouse',
                            tooltip: 'bottomLeft'
                          }
                        },
                        adjust: {y: 10,
                                 screen: true,
                                 mouse: false}
                      });}
    });
});

