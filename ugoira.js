
var system = require('system'),
    page = require('webpage').create();
    args = system.args;

page.settings.loadImages = false;
page.open(args[1], function (status) {
    if (status !== 'success') {
        console.error("Opening the page didn't succeed");
    } else {
        console.log(page.evaluate(function() {
            var data = pixiv.context.ugokuIllustData,
                parse = [data.src];
            for (var i in data.frames) {
                parse.push(data.frames[i].delay);
            }
            return parse;
        }));
    }
    phantom.exit();
});

