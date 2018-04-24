# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
# This is a Shiny web application for clickstream data.
# 
# Displays:
# 
# Click records, past 1-24 hours.
# - Top categories, facet by ad/country/purchase
# - Map view based on country
# 
# Ad serve records, past 1-24 hours.
# - Top categories, facet by ad
#
# Ad buys and conversion rate
#
# Ad latency rate
#

dyn.load("/Library/Java/JavaVirtualMachines/jdk-9.0.1.jdk/Contents/Home/lib/server/libjvm.dylib")
library(shiny)
library(RJDBC)
library(ggplot2)
library(dplyr)
library(rworldmap)
library(maps)
library(reshape2)
library(AWR.Athena)
require(DBI)

# Define UI for application that draws clickstream plots 
ui <- fluidPage(
   
  navbarPage("Promotions",
             tabPanel("Clicks",
                      sidebarLayout(
                        sidebarPanel(
                          sliderInput("timerange",
                                      "Time range (hours):",
                                      min = 1,
                                      max = 24,
                                      value = 1),
                          selectInput(inputId = "facet", label = strong("Grouping"),
                                      choices = c('offerid','countrycode','rating'),
                                      selected = "offerid")
                          
                        ),
                        
                        # Show a plot of the enhanced clickstream data for those hours
                        mainPanel(
                          plotOutput("enhClickPlot")
                        )
                      )),
             tabPanel("Ads",
                      sidebarLayout(
                        sidebarPanel(
                          sliderInput("adtimerange",
                                      "Time range (hours):",
                                      min = 1,
                                      max = 24,
                                      value = 1)
                        ),
                        
                        # Show a plot of the ad data for those hours
                        mainPanel(
                          plotOutput("adPlot")
                        )
                      )),
             tabPanel("Activity",
                      sidebarLayout(
                        sidebarPanel(
                          sliderInput("maptimerange",
                                      "Time range (hours):",
                                      min = 1,
                                      max = 24,
                                      value = 1)
                        ),
                        
                        # Show a map of the clickstream data 
                        mainPanel(
                          plotOutput("mapPlot")
                        )
                      )),
             tabPanel("Ad Conversions",
                      fluidRow(
                          column(5, plotOutput("adConvPlot"))
                      )
             ),
             tabPanel("Ad Latency", plotOutput("adLatencyPlot")
             )
             )
)

# Define server logic required to draw a requested plots
server <- function(input, output) {
   
  enhClickDataR  = reactive({
    req(input$timerange, input$facet)
    conn <- dbConnect(AWR.Athena::Athena(), 
                      region='us-east-1', 
                      s3_staging_dir='s3://aws-athena-query-results--us-east-1/',
                      schema_name='default')
    
    # reflect UTC offset
    cday = as.POSIXlt(Sys.time(), tz="GMT") 
    dday = cday - as.difftime(1, units="days")
    data <- dbGetQuery(conn, paste("SELECT * FROM promodb.ecclicksenh ",
                                   "where (year = '", format(cday, "%Y"), "' or year = '", format(dday, "%Y"),  "') ",
                                   "and (month = '", format(cday, "%m"), "' or month = '", format(dday, "%m"),  "') ",
                                   "and (day = '", format(cday, "%d"), "' or day = '", format(dday, "%d"),  "') ",
                                   sep=''))
    dbDisconnect(conn)
    data
    
  })
  adDataR  = reactive({
    req(input$adtimerange)
    conn <- dbConnect(AWR.Athena::Athena(), 
                      region='us-east-1', 
                      s3_staging_dir='s3://aws-athena-query-results--us-east-1/', 
                      schema_name='default')
    
    # reflect UTC offset
    cday = as.POSIXlt(Sys.time(), tz="GMT") 
    dday = cday - as.difftime(1, units="days")
    data <- dbGetQuery(conn, paste("SELECT * FROM promodb.ecadserve ",
                                   "where (year = '", format(cday, "%Y"), "' or year = '", format(dday, "%Y"),  "') ",
                                   "and (month = '", format(cday, "%m"), "' or month = '", format(dday, "%m"),  "') ",
                                   "and (day = '", format(cday, "%d"), "' or day = '", format(dday, "%d"),  "') ",
                                   sep=''))
    dbDisconnect(conn)
    data
    
  })
  
  adConvDataR  = reactive({
    conn <- dbConnect(AWR.Athena::Athena(), 
                      region='us-east-1', 
                      s3_staging_dir='s3://aws-athena-query-results--us-east-1/', 
                      schema_name='default')
    
    data <- dbGetQuery(conn, "SELECT distinct(a.offerid) as offerid,  ( select count(b.offerid) from promodb.ecclicksenh b  where b.offerid = offerid ) as total_buys, ( select count(c.offerid) from promodb.ecadserve c  where c.offerid = offerid) as total_serves FROM promodb.ecadserve a")
    dbDisconnect(conn)
    data
    
  })
  adLatencyDataR  = reactive({
    conn <- dbConnect(AWR.Athena::Athena(), 
                      region='us-east-1', 
                      s3_staging_dir='s3://aws-athena-query-results--us-east-1/', 
                      schema_name='default')
    
    cday = as.numeric(Sys.time()) - 3600*24
    query = paste("select a.offerid, a.ts as serve_time, a.clickts as click_time, a.category from promodb.ecadserve a where cast(regexp_replace(coalesce(a.ts, '0'), '[a-zA-Z]+', '') as decimal) > ", cday, sep="")
    data <- dbGetQuery(conn, query)
    dbDisconnect(conn)
    data
    
  })
  
   output$enhClickPlot <- renderPlot({
     enhClickData = enhClickDataR()
     enhClickData$item = as.factor(enhClickData$item)
     enhClickData$userid = as.factor(enhClickData$userid)
     enhClickData$category = as.factor(enhClickData$category)
     enhClickData$rating = as.factor(enhClickData$rating)
     enhClickData$timestamp = as.POSIXct(paste(
       enhClickData$year, enhClickData$month,
       enhClickData$day, enhClickData$hour,
       sep='-'
     ), format="%Y-%m-%d-%H")
     
      facet = input$facet
      # reflect UTC offset
      cday = as.POSIXlt(Sys.time(), tz="GMT") 
      dday = cday - as.difftime(input$timerange, units="hours")
      relevantData = filter(enhClickData, timestamp >= dday)
      ggplot(relevantData, aes(category)) + 
        geom_bar(aes_string(fill=facet)) +
        coord_flip() +
        ggtitle("Enhanced clickstream data") +
        xlab("Product category") +
        ylab(paste("Clicks in last ", input$timerange, " hour(s)", sep=''))
   })
   output$adPlot <- renderPlot({
     adData = adDataR()
     adData$category = as.factor(adData$category)
     adData$offerid = as.factor(adData$offerid)
     adData$timestamp = as.POSIXct(paste(
       adData$year, adData$month,
       adData$day, adData$hour,
       sep='-'
     ), format="%Y-%m-%d-%H")
     
     # reflect UTC offset
     cday = as.POSIXlt(Sys.time(), tz="GMT") 
     dday = cday - as.difftime(input$adtimerange, units="hours")
     relevantData = filter(adData, timestamp >= dday)
     ggplot(relevantData, aes(category)) + 
       geom_bar(aes(fill=offerid)) +
       coord_flip() +
       ggtitle("Ad serves") +
       xlab("Product category") +
       ylab(paste("Ads served in last ", input$adtimerange, " hour(s)", sep=''))
   }) 
   
   output$mapPlot <- renderPlot({
     enhClickData = enhClickDataR()
     enhClickData$item = as.factor(enhClickData$item)
     enhClickData$userid = as.factor(enhClickData$userid)
     enhClickData$category = as.factor(enhClickData$category)
     enhClickData$countrycode = toupper(enhClickData$countrycode)
     enhClickData$offerid = as.factor(enhClickData$offerid)
     enhClickData$timestamp = as.POSIXct(paste(
       enhClickData$year, enhClickData$month,
       enhClickData$day, enhClickData$hour,
       sep='-'
     ), format="%Y-%m-%d-%H")
     
     # reflect UTC offset
     cday = as.POSIXlt(Sys.time(), tz="GMT") 
     dday = cday - as.difftime(input$maptimerange, units="hours")
     relevantData = filter(enhClickData, timestamp >= dday)
     
     if(nrow(relevantData) > 0) {
       totals = count(relevantData, countrycode)
       ccmap <- joinCountryData2Map(totals, joinCode="ISO2", nameJoinColumn="countrycode")
       
       mapCountryData(ccmap, nameColumnToPlot="n", mapTitle="Map of click activity",
                      colourPalette="terrain")
     }
     
   })
   
   output$adConvPlot <- renderPlot({
     adData = adConvDataR()
     adData$offerid = as.factor(adData$offerid)
     
     # each row has an ad, total serves, and total buys
     data.m <- melt(adData, id.vars='offerid')
     ggplot(data.m, aes(offerid, value)) + 
       geom_bar(aes(fill = variable), position = "dodge", stat="identity") +
       ggtitle("Ad conversions") +
       xlab("Offer ID") +
       ylab("Ad serves and conversions")
   }) 
   output$adLatencyPlot<- renderPlot({
     adData = adLatencyDataR()
     adData$category = as.factor(adData$category)
     adData$latency = as.numeric(adData$serve_time) - as.numeric(adData$click_time)
     adData$latency = pmax(adData$latency, 0)
     fdData = adData %>% filter(!is.na(latency))
     
     means = fdData %>% 
       group_by(category) %>% 
       summarise( avg_latency = mean(latency) )
     ggplot(means, aes(category, avg_latency)) + 
       geom_col() +
       coord_flip() +
       ggtitle("Ad latency, last 24 hours") +
       xlab("Product category") +
       ylab("Average latency (s)")
#    ggplot(fdData, aes(click_time, latency)) +
#      geom_point(color='blue') +
#      ggtitle("Ad latency") +
#      xlab("Time") +
#      ylab("Latency (s)")
   }) 
}

shinyApp(ui = ui, server = server)
