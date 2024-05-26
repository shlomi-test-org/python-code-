const createMrssXml = require("./createMrssXml");
const formatMrssXml = require("./formatMrssXml");
const mrssLib = require("./mrssLib");
const { fetchSiteInfo, getToken, getSiteMap, log } = mrssLib;
const { escapeXML } = require('xml-crypto');
// Function to sanitize string input (to prevent XSS)
function sanitizeAndEncode(input) {
    // Perform basic sanitization
    const sanitizedInput = input ? input.toString() : '';
    // Encode the sanitized input to prevent XSS
    return escapeXML(sanitizedInput);
}

module.exports = cache => (req, res) => {
    const host = req.headers.host;
    const path = req.originalUrl;
    let limit = parseInt(req.query.limit);
    let offset = parseInt(req.query.offset);
    let ptt = sanitizeAndEncode(req.query.ptt);
    let category = sanitizeAndEncode(req.query.category);
    let tag = sanitizeAndEncode(req.query.tag);

    // Sanitize limit input
    if (isNaN(limit) || limit > 100) {
        return res.status(400).send("Limit should be a number less than or equal to 100");
    }
    // Sanitize offset input
    if (isNaN(offset)) {
        offset = 0; // Default value if offset is not a number
    }

    res.set("Content-Type", "application/xml");
    fetchSiteInfo(host).then(data => {
        const site = data.gist.siteInternalName;
        getToken(site).then(data => {
            getSiteMap(
                site,
                data.authorizationToken,
                limit,
                offset,
                category,
                tag
            ).then(data => {
                const mrssXml = createMrssXml(data, ptt, host);
                const encodedXml = escapeXML(mrssXml);
                res.send(formatMrssXml(encodedXml, host));
            });
        });
    });
};
